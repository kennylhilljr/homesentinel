#!/bin/bash
# 2026-03-11: Generate self-signed SSL cert with SANs for all local + ZeroTier IPs.
# This lets you access HomeSentinel via https://<any-ip>:8443 without cert errors.
#
# Usage: ./scripts/gen-cert.sh [extra-ip ...]
#   e.g.: ./scripts/gen-cert.sh 10.147.17.42

set -e

CERT_DIR="$(dirname "$0")/../backend/certs"
mkdir -p "$CERT_DIR"

# Collect all IPs on this machine
ALL_IPS=$(ifconfig 2>/dev/null | grep 'inet ' | awk '{print $2}' | grep -v '^127\.' || true)

# Add any extra IPs passed as args
for ip in "$@"; do
  ALL_IPS="$ALL_IPS $ip"
done

# Build SAN list
SAN="DNS:localhost,DNS:homesentinel.local,IP:127.0.0.1"
idx=2
for ip in $ALL_IPS; do
  SAN="$SAN,IP:$ip"
  idx=$((idx + 1))
done

echo "Generating cert with SANs: $SAN"

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$CERT_DIR/key.pem" \
  -out "$CERT_DIR/cert.pem" \
  -days 3650 \
  -subj "/CN=HomeSentinel/O=HomeSentinel/C=US" \
  -addext "subjectAltName=$SAN"

echo ""
echo "Certificate generated at:"
echo "  $CERT_DIR/cert.pem"
echo "  $CERT_DIR/key.pem"
echo ""
echo "SANs included:"
echo "$SAN" | tr ',' '\n' | sed 's/^/  /'
echo ""
echo "To trust this cert on macOS:"
echo "  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_DIR/cert.pem"
