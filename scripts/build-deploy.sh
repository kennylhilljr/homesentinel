#!/bin/bash
# 2026-03-11: Build React frontend and prepare for FastAPI static serving.
# After running this, the entire app is served from FastAPI on port 8443.
#
# Usage: ./scripts/build-deploy.sh
#
# Result:
#   https://localhost:8443        → React dashboard
#   https://localhost:8443/api/*  → FastAPI backend
#   https://<zerotier-ip>:8443   → Same thing, works remotely

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "=== HomeSentinel Build & Deploy ==="
echo ""

# 1. Build React
echo "[1/3] Building React frontend..."
cd "$FRONTEND_DIR"
npm run build
echo "  React build complete."

# 2. Verify build output
if [ ! -f "$FRONTEND_DIR/build/index.html" ]; then
  echo "ERROR: build/index.html not found!"
  exit 1
fi

BUILD_SIZE=$(du -sh "$FRONTEND_DIR/build" | awk '{print $1}')
echo "  Build size: $BUILD_SIZE"
echo ""

# 3. Regenerate SSL cert (optional, if IPs changed)
echo "[2/3] Checking SSL certificates..."
if [ ! -f "$PROJECT_DIR/backend/certs/cert.pem" ]; then
  echo "  No cert found, generating..."
  "$SCRIPT_DIR/gen-cert.sh"
else
  echo "  Existing cert found. Run ./scripts/gen-cert.sh to regenerate with new IPs."
fi
echo ""

# 4. Print access info
echo "[3/3] Ready!"
echo ""
echo "Start the backend:"
echo "  cd $PROJECT_DIR/backend && python3 main.py"
echo ""
echo "Access HomeSentinel at:"
echo "  Local:     https://localhost:8443"

# Show ZeroTier IP if available
ZT_IP=$(ifconfig 2>/dev/null | grep -A2 'zt' | grep 'inet ' | awk '{print $2}' || true)
if [ -n "$ZT_IP" ]; then
  echo "  ZeroTier:  https://$ZT_IP:8443"
fi

# Show LAN IP
LAN_IP=$(ifconfig 2>/dev/null | grep -A2 'en0' | grep 'inet ' | awk '{print $2}' || true)
if [ -n "$LAN_IP" ]; then
  echo "  LAN:       https://$LAN_IP:8443"
fi

echo ""
echo "All routes served from a single port — no separate frontend server needed."
