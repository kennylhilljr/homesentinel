#!/bin/bash
# 2026-08-07: Generate a dedicated SSH key for HomeSentinel and install it on
# the Chester 5G router, so speed tests no longer need sshpass or a password.
#
# Usage: ./scripts/setup-chester-ssh-key.sh [host]
#   e.g.: ./scripts/setup-chester-ssh-key.sh 192.168.12.1
#
# You will be prompted for the Chester root password ONCE, to copy the public
# key over. After that the password is never used again.
#
# Env overrides (same names the backend reads):
#   CHESTER_SSH_HOST, CHESTER_SSH_PORT, CHESTER_SSH_USERNAME, CHESTER_SSH_KEY

set -euo pipefail

HOST="${1:-${CHESTER_SSH_HOST:-192.168.12.1}}"
PORT="${CHESTER_SSH_PORT:-22}"
USER="${CHESTER_SSH_USERNAME:-root}"
KEY="${CHESTER_SSH_KEY:-$HOME/.ssh/homesentinel_chester}"
KNOWN_HOSTS="${CHESTER_SSH_KNOWN_HOSTS:-$HOME/.ssh/homesentinel_known_hosts}"

echo "=== HomeSentinel Chester SSH key setup ==="
echo "Target: $USER@$HOST:$PORT"
echo "Key:    $KEY"
echo ""

# 1. Generate the key if it does not exist. ed25519 with no passphrase, since
#    the backend runs unattended. The key only grants access to the router.
if [ -f "$KEY" ]; then
  echo "Key already exists at $KEY, reusing it."
else
  mkdir -p "$(dirname "$KEY")"
  ssh-keygen -t ed25519 -N "" -C "homesentinel@$(hostname -s)" -f "$KEY"
  echo "Generated $KEY"
fi
chmod 600 "$KEY"
echo ""

# 2. Pin the router host key so the backend's trust-on-first-use store matches
#    what we verify here.
mkdir -p "$(dirname "$KNOWN_HOSTS")"
touch "$KNOWN_HOSTS"
chmod 600 "$KNOWN_HOSTS"
if ! ssh-keygen -F "[$HOST]:$PORT" -f "$KNOWN_HOSTS" >/dev/null 2>&1 \
   && ! ssh-keygen -F "$HOST" -f "$KNOWN_HOSTS" >/dev/null 2>&1; then
  echo "Fetching Chester host key fingerprint..."
  ssh-keyscan -p "$PORT" -H "$HOST" >> "$KNOWN_HOSTS" 2>/dev/null
  echo "Pinned host key for $HOST in $KNOWN_HOSTS:"
  ssh-keygen -lf "$KNOWN_HOSTS" | tail -n 2
  echo ""
  echo "Confirm this matches the router before continuing (Ctrl-C to abort)."
  read -r -p "Press Enter to continue... " _
fi
echo ""

# 3. Install the public key. Chester runs dropbear (OpenWrt-derived firmware),
#    which reads /etc/dropbear/authorized_keys, not ~/.ssh/authorized_keys.
#    Write to both so either SSH daemon picks it up.
PUBKEY="$(cat "$KEY.pub")"
echo "Installing public key on Chester (you'll be prompted for the root password)..."
ssh -p "$PORT" \
    -o UserKnownHostsFile="$KNOWN_HOSTS" \
    -o StrictHostKeyChecking=yes \
    -o PubkeyAuthentication=no \
    "$USER@$HOST" \
    "set -e
     for d in /etc/dropbear \$HOME/.ssh; do
       mkdir -p \"\$d\"
       chmod 700 \"\$d\"
       touch \"\$d/authorized_keys\"
       chmod 600 \"\$d/authorized_keys\"
       grep -qF '$PUBKEY' \"\$d/authorized_keys\" || echo '$PUBKEY' >> \"\$d/authorized_keys\"
     done"

echo ""
echo "Verifying key-only login..."
if ssh -p "$PORT" \
       -i "$KEY" \
       -o UserKnownHostsFile="$KNOWN_HOSTS" \
       -o StrictHostKeyChecking=yes \
       -o PasswordAuthentication=no \
       -o BatchMode=yes \
       -o ConnectTimeout=10 \
       "$USER@$HOST" 'echo ok' >/dev/null 2>&1; then
  echo "Key auth works."
else
  echo "Key auth did NOT work. The password fallback will keep speed tests running."
  echo "Common cause: Chester firmware wipes /etc/dropbear/authorized_keys on reboot."
  echo "Re-run this script after a router restart, or check the firmware's SSH settings."
  exit 1
fi

echo ""
echo "Done. Restart the backend to pick up the key:"
echo "  ./homesentinel-ctl.sh restart"
echo ""
echo "You can now clear CHESTER_SSH_PASSWORD / the Chester password in Settings"
echo "if nothing else needs it (the HTTP API still uses the admin password)."
