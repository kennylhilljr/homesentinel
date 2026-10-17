# HomeSentinel Backend — Deco Integration Notes

## Deco Local API (LuCI)

The TP-Link Deco mesh router exposes a local HTTP API on **port 80** using the LuCI framework.
Authentication uses RSA-encrypted passwords with AES-encrypted request/response bodies.
All of this is implemented in `services/deco_client.py`.

### Working Endpoints

| Endpoint | Form | Operation | Description |
|---|---|---|---|
| `admin/client?form=client_list` | `client_list` | `read` | Get all clients (or per-node with `device_mac` param) |
| `admin/client?form=client_list` | `client_list` | `write` | Write client info (name). **Does NOT persist across sessions** |
| `admin/device?form=device_list` | `device_list` | `read` | Get all Deco mesh nodes |
| `admin/network?form=performance` | `performance` | `read` | CPU/memory usage |
| `admin/network?form=wan_ipv4` | `wan_ipv4` | `read` | WAN IP info |
| `admin/system?form=logout` | `logout` | — | Logout / invalidate stok |

### Per-Node Client Mapping (2026-03-10)

To get clients connected to a **specific Deco node**, pass its MAC as `device_mac`:

```python
result = client._local_encrypted_request(
    "admin/client?form=client_list",
    json.dumps({"operation": "read", "params": {"device_mac": "8C-90-2D-2D-9A-20"}})
)
```

Use `device_mac: "default"` to get ALL clients across all nodes.

### Client Rename (2026-03-10) — DOES NOT PERSIST

The write operation returns `error_code: 0` but the name reverts on the next read.
The `name` field is auto-detected device fingerprinting and is **read-only** in practice.
Adding `user_set_name_type: True` to the payload does not help.

```python
# This "succeeds" (error_code: 0) but name reverts on next read
result = client._local_encrypted_request(
    "admin/client?form=client_list",
    json.dumps({
        "operation": "write",
        "params": {
            "device_mac": "default",
            "client_list": [{
                "mac": "74-EC-B2-12-0C-6D",
                "name": base64.b64encode("New Name".encode()).decode(),
                "user_set_name_type": True,
            }]
        }
    })
)
```

The Deco mobile app stores custom names in the **TP-Link cloud account**, not on the router.
HomeSentinel stores custom names locally in SQLite (`friendly_name` column in `network_devices`).

## Deco Ports

Scan of Deco master at `192.168.12.188` (2026-03-10):

| Port | Protocol | Service | Notes |
|---|---|---|---|
| 80 | HTTP | LuCI web UI | **Working** — used by `deco_client.py` |
| 443 | HTTPS | LuCI web UI (TLS) | Accepts TLS but ignores TSLP binary packets |
| 20001 | SSH | Dropbear SSH | Custom TP-Link SSH (`SSH-2.0-dropbear`). Auth fails with admin password — uses custom `TPUserAuthPasswordMethods` from Tether APK |
| 30001 | TCP | Unknown | Open but rejects TLS; no response to plain TCP |

## TMP Protocol (`tmp_client.py`)

Reverse-engineered from the TP-Link Tether APK (`com.tplink.tether v4.12.x`).

### Protocol Stack
```
Application (JSON payloads with opcodes)
  → Business Layer (2-byte header + JSON)
    → TMP Layer (16-byte header, CRC32, version negotiation)
      → TSLP Layer (24-byte header, channels, sequences)
        → TLS Socket
```

### Authentication: SPAKE2+ (RFC 9383)
- Curve: P-256, Hash: SHA-256, KDF: HKDF-SHA256, MAC: HMAC-SHA256
- Post-auth encryption: AES-128-CCM

### Key Opcodes
| Opcode | Hex | Action |
|---|---|---|
| 784 | 0x310 | GET client list |
| 785 | 0x311 | SET client info (rename) |

### Connection Status (2026-03-10): BLOCKED

The TMP client cannot connect because:
1. **Port 30001**: Rejects TLS handshake (`Connection reset by peer`)
2. **Port 443**: TLS connects but does not respond to TSLP auth packets (timeout)
3. **Port 20001 (SSH)**: Connects but authentication fails — TP-Link uses a custom SSH auth method (`TPUserAuthPasswordMethods`) that is not standard password auth

The Tether app connects via SSH on port 20001 using a custom JSch library (`TPSSession`),
then port-forwards to `localhost:20002` where TMP runs. The SSH auth uses a modified
key exchange hash for `TPS-` banners that hasn't been reverse-engineered.

### What Would Make It Work
1. Extract TP-Link's modified JSch JAR from the APK and use it directly via Java
2. Fully reverse-engineer `connectWithBannerPrefix()` (1622 bytecode instructions, not decompilable by JADX)
3. Or find the correct credential transformation for SSH auth

## Node Info (from `admin/device?form=device_list`)

Each node has these key fields:
- `mac`: Node MAC address (e.g., `8C-90-2D-2D-9A-20`)
- `nickname`: Base64-encoded display name
- `role`: `master` or `slave`
- `device_id`: Unique node identifier (e.g., `8019B0829D3DD28DFE1A39EDB91113862394E0AB`)
- `device_model`: Model string
- `connection_type`: How node connects to mesh (e.g., `["band2_4", "band5"]`)

## Client Info (from `admin/client?form=client_list`)

Each client has these key fields:
- `mac`: Client MAC (format: `AA-BB-CC-DD-EE-FF`)
- `name`: Base64-encoded auto-detected device name
- `online`: Boolean
- `wire_type`: `wireless` or `wired`
- `connection_type`: `band2_4`, `band5`, `band6`, or `wired`
- `owner_id`: TP-Link cloud account ID (not the node ID)
- `access_host`: Always `"1"` — not useful for per-node mapping
- `client_mesh`: Boolean
- `space_id`: Room/space identifier
- `interface`: `main` or `guest`
