#!/usr/bin/env python3
"""
TP-Link TMP (Tether Management Protocol) Client

Reverse-engineered from the TP-Link Tether Android APK (com.tplink.tether v4.12.x).
Implements the TSLP/TMP binary protocol over TLS for Deco mesh router management.

Protocol stack:
  Application (JSON payloads with opcodes)
    -> Business Layer (2-byte header + JSON)
      -> TMP Layer (16-byte header, CRC32, version negotiation)
        -> TSLP Layer (24-byte header, channels, sequences)
          -> TLS Socket (port from TPAP discovery or 443)

Authentication: SPAKE2+ (RFC 9383) with P-256 curve, HKDF-SHA256, HMAC-SHA256
Encryption: AES-128-CCM for post-auth business data
"""

import os
import sys
import ssl
import json
import struct
import socket
import base64
import hashlib
import hmac
import logging
import secrets
from binascii import hexlify, unhexlify
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TSLP Packet (24-byte header)
# ---------------------------------------------------------------------------
# | 0  | version (1B)        | always 0x01
# | 1  | type (1B)           | 0x01=request, 0x02=response
# | 2  | channelType (1B)    | 0x01=auth, 0x02=business
# | 3  | reserved (1B)       | 0x00
# | 4  | payloadLength (4B)  | big-endian int32
# | 8  | channel (8B)        | UTF-8 padded ("TMP\0...", "" for auth)
# | 16 | sequence (4B)       | big-endian int32
# | 20 | checksum (4B)       | CRC32 of entire packet
# | 24 | payload (N bytes)   |

TSLP_HEADER_SIZE = 24
TSLP_VERSION = 0x01
TSLP_TYPE_REQUEST = 0x01
TSLP_TYPE_RESPONSE = 0x02
TSLP_CHANNEL_AUTH = 0x01
TSLP_CHANNEL_BUSINESS = 0x02
CRC32_PLACEHOLDER = 0x92B1BDCD  # -1832963859 as unsigned

# TMP Packet types
TMP_TYPE_ASSOC_REQ = 1
TMP_TYPE_ASSOC_ACK = 2
TMP_TYPE_ASSOC_REFUSE = 3
TMP_TYPE_HEARTBEAT = 4
TMP_TYPE_DATA = 5
TMP_TYPE_CLOSE = 6

TMP_HEADER_SIZE = 16  # Full TMP header for types 4,5,6
TMP_GENERAL_HEADER_SIZE = 4  # Short header for types 1,2,3

# TMP version
TMP_MAJOR_VERSION = 2
TMP_MINOR_VERSION = 0


def _crc32(data: bytes) -> int:
    """Compute CRC32 matching Java's java.util.zip.CRC32."""
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF


def _make_channel_bytes(channel_name: str) -> bytes:
    """Encode channel name to 8-byte padded field."""
    encoded = channel_name.encode('utf-8')[:8]
    return encoded.ljust(8, b'\x00')


class TSLPPacket:
    """TSLP (TLS Protocol) packet."""

    def __init__(self, ptype: int, channel_type: int, channel: str,
                 sequence: int, payload: bytes):
        self.version = TSLP_VERSION
        self.type = ptype
        self.channel_type = channel_type
        self.channel = channel
        self.sequence = sequence
        self.payload = payload

    def encode(self) -> bytes:
        """Serialize packet with CRC32."""
        header = struct.pack(
            '>BBBB I 8s I I',
            self.version,
            self.type,
            self.channel_type,
            0x00,  # reserved
            len(self.payload),
            _make_channel_bytes(self.channel),
            self.sequence,
            0x00000000,  # CRC32 placeholder
        )
        packet = header + self.payload
        # Compute CRC32 over entire packet and write at offset 20
        crc = _crc32(packet)
        packet = packet[:20] + struct.pack('>I', crc) + packet[24:]
        return packet

    @classmethod
    def decode(cls, data: bytes) -> 'TSLPPacket':
        """Deserialize packet from bytes."""
        if len(data) < TSLP_HEADER_SIZE:
            raise ValueError(f"TSLP packet too short: {len(data)} bytes")
        version, ptype, channel_type, _, payload_len = struct.unpack('>BBBBI', data[:8])
        channel_raw = data[8:16]
        sequence, checksum = struct.unpack('>II', data[16:24])
        channel = channel_raw.rstrip(b'\x00').decode('utf-8', errors='replace')
        payload = data[24:24 + payload_len]
        return cls(ptype, channel_type, channel, sequence, payload)


class TMPPacket:
    """TMP layer packet."""

    def __init__(self, ptype: int, payload: bytes = b'',
                 sequence: int = 0, status: int = 0):
        self.major_version = TMP_MAJOR_VERSION
        self.minor_version = TMP_MINOR_VERSION
        self.type = ptype
        self.payload = payload
        self.sequence = sequence
        self.status = status

    def encode(self) -> bytes:
        """Serialize TMP packet."""
        if self.type in (TMP_TYPE_ASSOC_REQ, TMP_TYPE_ASSOC_ACK, TMP_TYPE_ASSOC_REFUSE):
            # 4-byte general header only
            return struct.pack('>BBBB',
                               self.major_version, self.minor_version,
                               self.type, 0x00)
        # 16-byte full header + payload
        header = struct.pack(
            '>BBBB HBB I I',
            self.major_version, self.minor_version,
            self.type, 0x00,
            len(self.payload) & 0xFFFF,
            self.status, 0x00,
            self.sequence,
            0x00000000,  # CRC32 placeholder
        )
        packet = header + self.payload
        crc = _crc32(packet)
        packet = packet[:12] + struct.pack('>I', crc) + packet[16:]
        return packet

    @classmethod
    def decode(cls, data: bytes) -> 'TMPPacket':
        """Deserialize TMP packet."""
        if len(data) < TMP_GENERAL_HEADER_SIZE:
            raise ValueError(f"TMP packet too short: {len(data)}")
        major, minor, ptype, _ = struct.unpack('>BBBB', data[:4])
        if ptype in (TMP_TYPE_ASSOC_REQ, TMP_TYPE_ASSOC_ACK, TMP_TYPE_ASSOC_REFUSE):
            pkt = cls(ptype)
            pkt.major_version = major
            pkt.minor_version = minor
            return pkt
        if len(data) < TMP_HEADER_SIZE:
            raise ValueError(f"TMP full packet too short: {len(data)}")
        payload_len, status, _ = struct.unpack('>HBB', data[4:8])
        sequence, checksum = struct.unpack('>II', data[8:16])
        payload = data[16:16 + payload_len]
        pkt = cls(ptype, payload, sequence, status)
        pkt.major_version = major
        pkt.minor_version = minor
        return pkt


class BusinessPacket:
    """Business layer packet (2-byte header + JSON)."""

    def __init__(self, btype: int = 1, bsubtype: int = 0, payload: bytes = b''):
        self.type = btype
        self.subtype = bsubtype
        self.payload = payload

    def encode(self) -> bytes:
        return struct.pack('>BB', self.type, self.subtype) + self.payload

    @classmethod
    def decode(cls, data: bytes) -> 'BusinessPacket':
        if len(data) < 2:
            raise ValueError("Business packet too short")
        btype, bsubtype = struct.unpack('>BB', data[:2])
        return cls(btype, bsubtype, data[2:])


# ---------------------------------------------------------------------------
# SPAKE2+ Implementation (simplified for TP-Link's cipher suite 1)
# Curve: P-256, Hash: SHA-256, KDF: HKDF-SHA256, MAC: HMAC-SHA256
# ---------------------------------------------------------------------------

try:
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256R1, generate_private_key, EllipticCurvePublicKey,
        EllipticCurvePrivateKey, ECDH
    )
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature, encode_dss_signature
    )
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESCCM
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# SPAKE2+ P-256 M and N points (RFC 9383 Appendix)
# M = HashToPoint("SPAKE2+-P256-SHA256-HKDF-SHA256-HMAC-SHA256 M")
# N = HashToPoint("SPAKE2+-P256-SHA256-HKDF-SHA256-HMAC-SHA256 N")
# These are the standard test vectors for P-256
SPAKE2P_M_X = 0x886e2f97ace46e55ba9dd7242579f2993b64e16ef3dcab95afd497333d8fa12f
SPAKE2P_M_Y = 0x5ff355163e43ce224e0b0e65ff02ac8e5c7be09419c785e0ca547d55a12e2d20
SPAKE2P_N_X = 0xd8bbd6c639c62937b04d997f38c3770719c629d7014d49a24b4f98baa1292b49
SPAKE2P_N_Y = 0x07d60aa6bfade45008a636337f5168c64d9bd36034808cd564490b1e656edbe7

# P-256 curve order
P256_ORDER = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551
P256_P = 0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff


def _int_to_bytes(n: int, length: int = 32) -> bytes:
    return n.to_bytes(length, 'big')


def _bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, 'big')


def _point_to_bytes(x: int, y: int) -> bytes:
    """Uncompressed point encoding (0x04 || x || y)."""
    return b'\x04' + _int_to_bytes(x) + _int_to_bytes(y)


def _mod_inv(a: int, m: int) -> int:
    """Modular inverse using extended Euclidean algorithm."""
    return pow(a, -1, m)


def _ec_add(x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int]:
    """Point addition on P-256."""
    p = P256_P
    if x1 == x2 and y1 == y2:
        # Point doubling
        lam = (3 * x1 * x1 + (P256_P - 3)) * _mod_inv(2 * y1, p) % p
    else:
        lam = (y2 - y1) * _mod_inv(x2 - x1, p) % p
    x3 = (lam * lam - x1 - x2) % p
    y3 = (lam * (x1 - x3) - y1) % p
    return x3, y3


def _ec_mul(k: int, x: int, y: int) -> Tuple[int, int]:
    """Scalar multiplication on P-256 using double-and-add."""
    rx, ry = None, None
    qx, qy = x, y
    while k > 0:
        if k & 1:
            if rx is None:
                rx, ry = qx, qy
            else:
                rx, ry = _ec_add(rx, ry, qx, qy)
        qx, qy = _ec_add(qx, qy, qx, qy)
        k >>= 1
    return rx, ry


# P-256 generator point
P256_GX = 0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296
P256_GY = 0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5


class Spake2PlusClient:
    """SPAKE2+ client implementation for TP-Link TMP protocol."""

    def __init__(self, password: str, username: str = "admin"):
        self.password = password
        self.username = username
        self.user_random = secrets.token_bytes(32)
        self._x = None  # Client private scalar
        self._X = None  # Client public share
        self._shared_key = None
        self._session_key = None
        self._confirm_key_client = None
        self._confirm_key_server = None

    def get_register_params(self) -> Dict[str, Any]:
        """Build pake_register request params."""
        return {
            "method": "login",
            "params": {
                "sub_method": "pake_register",
                "username": self.username,
                "user_random": hexlify(self.user_random).decode(),
                "cipher_suites": [1],
                "encryption": ["aes_128_ccm"],
            }
        }

    def process_register_response(self, resp: Dict) -> None:
        """Process pake_register response and prepare SPAKE2+ share."""
        self.dev_random = unhexlify(resp["dev_random"])
        self.dev_salt = unhexlify(resp["dev_salt"])
        self.dev_share_hex = resp["dev_share"]
        self.iterations = resp.get("iterations", 10000)
        self.extra_crypt = resp.get("extra_crypt", {})
        self.encryption = resp.get("encryption", "aes_128_ccm")

    def _process_password(self) -> bytes:
        """Process password through extra_crypt shadow function."""
        extra = self.extra_crypt
        if not extra:
            # Default: username/password
            return (self.username + "/" + self.password).encode()

        crypt_type = extra.get("type", "")
        params = extra.get("params", {})

        if crypt_type == "password_shadow":
            passwd_id = params.get("passwd_id", 1)
            if passwd_id == 1:
                # MD5 crypt
                return hashlib.md5(self.password.encode()).hexdigest().encode()
            elif passwd_id == 2:
                # SHA1
                return hashlib.sha1(self.password.encode()).hexdigest().encode()
            elif passwd_id == 5:
                # SHA256 crypt
                return hashlib.sha256(self.password.encode()).hexdigest().encode()
            elif passwd_id == 3:
                # SHA1 with username + MAC
                mac = params.get("mac", "")
                combined = self.username + mac + self.password
                return hashlib.sha1(combined.encode()).hexdigest().encode()
            else:
                return hashlib.md5(self.password.encode()).hexdigest().encode()

        elif crypt_type == "password_sha_with_salt":
            salt = params.get("salt", "")
            role = params.get("role", "admin")
            combined = role + salt + self.password
            return hashlib.sha256(combined.encode()).hexdigest().encode()

        # Fallback
        return self.password.encode()

    def compute_share(self) -> Dict[str, Any]:
        """Compute SPAKE2+ client share X and confirmation cA."""
        # 1. Process password
        pw_bytes = self._process_password()

        # 2. PBKDF2 to derive w0 and w1
        # Key material = PBKDF2(password, salt, iterations, 64 bytes)
        dk = hashlib.pbkdf2_hmac(
            'sha256', pw_bytes, self.dev_salt, self.iterations, dklen=64
        )
        w0 = _bytes_to_int(dk[:32]) % P256_ORDER
        w1 = _bytes_to_int(dk[32:64]) % P256_ORDER

        # 3. Generate random x and compute X = x*G + w0*M
        self._x = _bytes_to_int(secrets.token_bytes(32)) % P256_ORDER
        xG_x, xG_y = _ec_mul(self._x, P256_GX, P256_GY)
        w0M_x, w0M_y = _ec_mul(w0, SPAKE2P_M_X, SPAKE2P_M_Y)
        X_x, X_y = _ec_add(xG_x, xG_y, w0M_x, w0M_y)
        self._X = (X_x, X_y)

        # 4. Parse server's share Y
        dev_share_bytes = unhexlify(self.dev_share_hex)
        if dev_share_bytes[0] == 0x04:
            Y_x = _bytes_to_int(dev_share_bytes[1:33])
            Y_y = _bytes_to_int(dev_share_bytes[33:65])
        else:
            raise ValueError("Unsupported point encoding")

        # 5. Compute shared secret: Z = x * (Y - w0*N)
        w0N_x, w0N_y = _ec_mul(w0, SPAKE2P_N_X, SPAKE2P_N_Y)
        # Negate w0N: (x, -y mod p)
        neg_w0N_y = P256_P - w0N_y
        # Y - w0*N
        Yp_x, Yp_y = _ec_add(Y_x, Y_y, w0N_x, neg_w0N_y)
        Z_x, Z_y = _ec_mul(self._x, Yp_x, Yp_y)

        # 6. Also compute V = w1 * (Y - w0*N)
        V_x, V_y = _ec_mul(w1, Yp_x, Yp_y)

        # 7. Build transcript TT for key schedule
        # Context = "PAKE V1" + user_random + dev_random
        context = b"PAKE V1" + self.user_random + self.dev_random

        # TT = len(context) || context || len(idProver) || idProver ||
        #      len(idVerifier) || idVerifier || len(M) || M || len(N) || N ||
        #      len(X) || X || len(Y) || Y || len(Z) || Z || len(V) || V ||
        #      len(w0) || w0
        def _len_prefix(data: bytes) -> bytes:
            return struct.pack('<Q', len(data)) + data

        X_bytes = _point_to_bytes(X_x, X_y)
        Y_bytes = dev_share_bytes
        Z_bytes = _point_to_bytes(Z_x, Z_y)
        V_bytes = _point_to_bytes(V_x, V_y)
        M_bytes = _point_to_bytes(SPAKE2P_M_X, SPAKE2P_M_Y)
        N_bytes = _point_to_bytes(SPAKE2P_N_X, SPAKE2P_N_Y)
        w0_bytes = _int_to_bytes(w0)

        tt = b''
        tt += _len_prefix(context)
        tt += _len_prefix(b'')  # idProver (empty)
        tt += _len_prefix(b'')  # idVerifier (empty)
        tt += _len_prefix(M_bytes)
        tt += _len_prefix(N_bytes)
        tt += _len_prefix(X_bytes)
        tt += _len_prefix(Y_bytes)
        tt += _len_prefix(Z_bytes)
        tt += _len_prefix(V_bytes)
        tt += _len_prefix(w0_bytes)

        # 8. Hash TT to get Ka || Ke
        tt_hash = hashlib.sha256(tt).digest()
        Ka = tt_hash[:16]
        Ke = tt_hash[16:]

        # 9. Derive confirmation keys using HKDF
        # KcA || KcB = HKDF(Ka, "ConfirmationKeys")
        if HAS_CRYPTO:
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=64,
                salt=None,
                info=b"ConfirmationKeys",
                backend=default_backend()
            )
            kc = hkdf.derive(Ka)
        else:
            # Simple HKDF fallback
            prk = hmac.new(b'\x00' * 32, Ka, hashlib.sha256).digest()
            kc = hmac.new(prk, b"ConfirmationKeys\x01", hashlib.sha256).digest()
            kc += hmac.new(prk, kc + b"ConfirmationKeys\x02", hashlib.sha256).digest()
            kc = kc[:64]

        KcA = kc[:32]
        KcB = kc[32:64]

        # 10. Compute confirmations
        # cA = HMAC(KcA, Y)
        # cB = HMAC(KcB, X)
        cA = hmac.new(KcA, Y_bytes, hashlib.sha256).digest()
        self._expected_cB = hmac.new(KcB, X_bytes, hashlib.sha256).digest()

        # 11. Session key = Ke
        self._session_key = Ke

        return {
            "method": "login",
            "params": {
                "sub_method": "pake_share",
                "user_share": hexlify(X_bytes).decode(),
                "user_confirm": hexlify(cA).decode(),
            }
        }

    def verify_share_response(self, resp: Dict) -> bool:
        """Verify server's confirmation and extract session token."""
        dev_confirm = unhexlify(resp["dev_confirm"])
        self.stok = resp.get("stok", "")
        self.start_seq = resp.get("start_seq", 0)

        if dev_confirm != self._expected_cB:
            logger.error("SPAKE2+ server confirmation mismatch!")
            return False

        logger.info(f"SPAKE2+ authentication successful! stok={self.stok[:20]}...")
        return True

    def get_session_key(self) -> bytes:
        return self._session_key

    def encrypt(self, plaintext: bytes, nonce: bytes) -> bytes:
        """Encrypt with AES-128-CCM."""
        if HAS_CRYPTO:
            aesccm = AESCCM(self._session_key[:16], tag_length=8)
            return aesccm.encrypt(nonce, plaintext, None)
        raise RuntimeError("cryptography library required for encryption")

    def decrypt(self, ciphertext: bytes, nonce: bytes) -> bytes:
        """Decrypt with AES-128-CCM."""
        if HAS_CRYPTO:
            aesccm = AESCCM(self._session_key[:16], tag_length=8)
            return aesccm.decrypt(nonce, ciphertext, None)
        raise RuntimeError("cryptography library required for decryption")


# ---------------------------------------------------------------------------
# TMP Client
# ---------------------------------------------------------------------------

class TMPClient:
    """TP-Link TMP protocol client for Deco mesh routers."""

    def __init__(self, host: str, port: int = 30001, password: str = "",
                 username: str = "admin"):
        self.host = host
        self.port = port
        self.password = password
        self.username = username
        self._sock = None
        self._ssl_sock = None
        self._seq = 0
        self._tmp_seq = 0
        self._spake = None
        self._authenticated = False

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _next_tmp_seq(self) -> int:
        self._tmp_seq += 1
        return self._tmp_seq

    def connect(self) -> None:
        """Establish TLS connection to Deco."""
        logger.info(f"Connecting to {self.host}:{self.port}...")
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # Allow older TLS versions that Deco might require
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        self._sock = socket.create_connection((self.host, self.port), timeout=10)
        self._ssl_sock = ctx.wrap_socket(self._sock, server_hostname=self.host)
        logger.info(f"TLS connected: {self._ssl_sock.version()}")

    def _send_tslp(self, channel_type: int, channel: str, payload: bytes) -> None:
        """Send a TSLP packet."""
        pkt = TSLPPacket(TSLP_TYPE_REQUEST, channel_type, channel,
                         self._next_seq(), payload)
        data = pkt.encode()
        logger.debug(f"TX TSLP: type={channel_type} ch={channel!r} "
                     f"seq={pkt.sequence} payload={len(payload)}B")
        self._ssl_sock.sendall(data)

    def _recv_tslp(self) -> TSLPPacket:
        """Receive a TSLP packet."""
        # Read 24-byte header
        header = b''
        while len(header) < TSLP_HEADER_SIZE:
            chunk = self._ssl_sock.recv(TSLP_HEADER_SIZE - len(header))
            if not chunk:
                raise ConnectionError("Connection closed while reading TSLP header")
            header += chunk

        _, _, _, _, payload_len = struct.unpack('>BBBBI', header[:8])
        # Read payload
        payload = b''
        while len(payload) < payload_len:
            chunk = self._ssl_sock.recv(payload_len - len(payload))
            if not chunk:
                raise ConnectionError("Connection closed while reading TSLP payload")
            payload += chunk

        return TSLPPacket.decode(header + payload)

    def _send_auth_json(self, data: Dict) -> Dict:
        """Send JSON on auth channel and receive response."""
        payload = json.dumps(data).encode('utf-8')
        self._send_tslp(TSLP_CHANNEL_AUTH, "", payload)
        resp_pkt = self._recv_tslp()
        logger.debug(f"RX auth: {resp_pkt.payload[:200]}")
        return json.loads(resp_pkt.payload.decode('utf-8'))

    def authenticate(self) -> bool:
        """Perform SPAKE2+ authentication."""
        self._spake = Spake2PlusClient(self.password, self.username)

        # Step 1: pake_register
        logger.info("SPAKE2+ Step 1: pake_register")
        register_req = self._spake.get_register_params()
        register_resp = self._send_auth_json(register_req)
        logger.info(f"Register response: sub_method={register_resp.get('sub_method')}, "
                     f"cipher_suites={register_resp.get('cipher_suites')}, "
                     f"iterations={register_resp.get('iterations')}")

        if "error_code" in register_resp and register_resp["error_code"] != 0:
            logger.error(f"Register failed: {register_resp}")
            return False

        self._spake.process_register_response(register_resp)

        # Step 2: pake_share
        logger.info("SPAKE2+ Step 2: pake_share")
        share_req = self._spake.compute_share()
        share_resp = self._send_auth_json(share_req)
        logger.info(f"Share response keys: {list(share_resp.keys())}")

        if "error_code" in share_resp and share_resp["error_code"] != 0:
            logger.error(f"Share failed: {share_resp}")
            return False

        # Step 3: Verify
        if not self._spake.verify_share_response(share_resp):
            logger.error("SPAKE2+ verification failed")
            return False

        self._authenticated = True
        return True

    def _send_tmp_business(self, opcode: int, params: Dict) -> Dict:
        """Send a TMP business request and receive response."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated")

        # Build JSON payload with params wrapper
        json_payload = json.dumps({
            "params": params,
        }).encode('utf-8')

        # Business packet: 2-byte header + opcode mapping
        # The opcode is embedded in the TMP layer, business layer just wraps JSON
        biz = BusinessPacket(1, 0, json_payload)
        biz_data = biz.encode()

        # TMP DATA packet
        tmp_pkt = TMPPacket(TMP_TYPE_DATA, biz_data, self._next_tmp_seq())
        tmp_data = tmp_pkt.encode()

        # Encrypt if we have a session key
        if self._spake and self._spake.get_session_key():
            nonce = struct.pack('>I', self._tmp_seq).rjust(13, b'\x00')
            try:
                encrypted = self._spake.encrypt(tmp_data, nonce)
                self._send_tslp(TSLP_CHANNEL_BUSINESS, "TMP", encrypted)
            except Exception as e:
                logger.warning(f"Encryption failed ({e}), sending plaintext")
                self._send_tslp(TSLP_CHANNEL_BUSINESS, "TMP", tmp_data)
        else:
            self._send_tslp(TSLP_CHANNEL_BUSINESS, "TMP", tmp_data)

        # Receive response
        resp_tslp = self._recv_tslp()
        resp_data = resp_tslp.payload

        # Try decryption
        if self._spake and self._spake.get_session_key():
            try:
                nonce = struct.pack('>I', self._tmp_seq).rjust(13, b'\x00')
                resp_data = self._spake.decrypt(resp_data, nonce)
            except Exception:
                pass  # May be plaintext

        # Parse TMP packet
        try:
            tmp_resp = TMPPacket.decode(resp_data)
            if tmp_resp.type == TMP_TYPE_DATA and tmp_resp.payload:
                biz_resp = BusinessPacket.decode(tmp_resp.payload)
                return json.loads(biz_resp.payload.decode('utf-8'))
        except Exception as e:
            logger.warning(f"Failed to parse TMP response: {e}")
            # Return raw for debugging
            return {"raw": resp_data.hex()[:200]}

        return {}

    def version_negotiate(self) -> bool:
        """Send TMP version association request."""
        logger.info("TMP version association...")
        assoc = TMPPacket(TMP_TYPE_ASSOC_REQ)
        assoc_data = assoc.encode()

        # May need encryption
        if self._spake and self._spake.get_session_key():
            nonce = struct.pack('>I', 0).rjust(13, b'\x00')
            try:
                encrypted = self._spake.encrypt(assoc_data, nonce)
                self._send_tslp(TSLP_CHANNEL_BUSINESS, "TMP", encrypted)
            except Exception:
                self._send_tslp(TSLP_CHANNEL_BUSINESS, "TMP", assoc_data)
        else:
            self._send_tslp(TSLP_CHANNEL_BUSINESS, "TMP", assoc_data)

        resp = self._recv_tslp()
        resp_data = resp.payload
        if self._spake and self._spake.get_session_key():
            try:
                nonce = struct.pack('>I', 0).rjust(13, b'\x00')
                resp_data = self._spake.decrypt(resp_data, nonce)
            except Exception:
                pass

        try:
            tmp_resp = TMPPacket.decode(resp_data)
            if tmp_resp.type == TMP_TYPE_ASSOC_ACK:
                logger.info("TMP version association successful")
                return True
            elif tmp_resp.type == TMP_TYPE_ASSOC_REFUSE:
                logger.error("TMP version association refused")
                return False
        except Exception as e:
            logger.warning(f"Version negotiate parse error: {e}")

        return False

    def rename_client(self, mac: str, new_name: str) -> Dict:
        """Rename a client device using TMP opcode 0x311 (785)."""
        # Normalize MAC to AA-BB-CC-DD-EE-FF
        mac_clean = mac.lower().replace(":", "").replace("-", "").replace(" ", "")
        if len(mac_clean) != 12:
            raise ValueError(f"Invalid MAC: {mac}")

        # Base64 encode the name (TP-Link convention)
        name_b64 = base64.b64encode(new_name.encode('utf-8')).decode('ascii')

        params = {
            "mac": mac_clean,
            "name": name_b64,
            "user_set_name_type": True,
            "client_type": "",
            "owner_id": 0,
            "enable_priority": False,
            "time_period": 0,
        }

        logger.info(f"Sending rename: MAC={mac_clean} name='{new_name}' (b64={name_b64})")
        return self._send_tmp_business(785, params)

    def get_client_list(self) -> Dict:
        """Get client list using TMP opcode 0x310 (784)."""
        return self._send_tmp_business(784, {"start_index": 0, "amount": 0})

    def close(self) -> None:
        """Close connection."""
        try:
            if self._ssl_sock:
                # Send TMP CLOSE
                close_pkt = TMPPacket(TMP_TYPE_CLOSE)
                self._send_tslp(TSLP_CHANNEL_BUSINESS, "TMP", close_pkt.encode())
        except Exception:
            pass
        try:
            if self._ssl_sock:
                self._ssl_sock.close()
        except Exception:
            pass
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    import sqlite3

    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s')

    parser = argparse.ArgumentParser(description="TP-Link TMP Client")
    parser.add_argument("--host", default="192.168.12.188")
    parser.add_argument("--port", type=int, default=30001)
    parser.add_argument("--action", choices=["discover", "rename", "clients"],
                        default="discover")
    parser.add_argument("--mac", help="MAC address for rename")
    parser.add_argument("--name", help="New name for rename")
    args = parser.parse_args()

    # Load password from DB
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "homesentinel.db")
    password = ""
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'deco_credentials'").fetchone()
        conn.close()
        if row:
            creds = json.loads(row[0])
            password = creds.get("password", "")
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")

    if not password:
        logger.error("No password found. Configure Deco credentials first.")
        return

    client = TMPClient(args.host, args.port, password)
    try:
        # Step 1: Connect
        client.connect()

        # Step 2: Authenticate
        if client.authenticate():
            logger.info("Authentication successful!")

            # Step 3: Version negotiate
            if client.version_negotiate():
                if args.action == "clients":
                    result = client.get_client_list()
                    print(json.dumps(result, indent=2))
                elif args.action == "rename":
                    if not args.mac or not args.name:
                        print("--mac and --name required for rename")
                        return
                    result = client.rename_client(args.mac, args.name)
                    print(json.dumps(result, indent=2))
                else:
                    print("Connected and authenticated successfully!")
            else:
                logger.error("Version negotiation failed")
        else:
            logger.error("Authentication failed")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
