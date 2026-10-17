#!/bin/bash
set -euo pipefail

RUNTIME_ROOT="$HOME/Library/Application Support/HomeSentinel"
AGENT_ROOT="$HOME/Library/LaunchAgents"
BACKUP_POINTER="$RUNTIME_ROOT/latest-plist-backup"
BACKEND_LABEL="com.homesentinel.backend"
FRONTEND_LABEL="com.homesentinel.frontend"
BACKEND_PLIST_NAME="com.homesentinel.backend.plist"
FRONTEND_PLIST_NAME="com.homesentinel.frontend.plist"
BACKEND_PLIST="$AGENT_ROOT/$BACKEND_PLIST_NAME"
FRONTEND_PLIST="$AGENT_ROOT/$FRONTEND_PLIST_NAME"
USER_DOMAIN="gui/$(id -u)"

if [ ! -f "$BACKUP_POINTER" ]; then
  echo "No plist-backups pointer found; refusing to guess a restore source." >&2
  exit 1
fi

BACKUP_ROOT="$(head -n 1 "$BACKUP_POINTER")"
if [ ! -d "$BACKUP_ROOT" ]; then
  echo "Launch-agent backup is missing: $BACKUP_ROOT" >&2
  exit 1
fi

launchctl bootout "$USER_DOMAIN/$BACKEND_LABEL" 2>/dev/null || true
launchctl bootout "$USER_DOMAIN/$FRONTEND_LABEL" 2>/dev/null || true

for name in "$BACKEND_PLIST_NAME" "$FRONTEND_PLIST_NAME"; do
  if [ -f "$BACKUP_ROOT/$name" ]; then
    cp -p "$BACKUP_ROOT/$name" "$AGENT_ROOT/$name"
    plutil -lint "$AGENT_ROOT/$name"
    launchctl bootstrap "$USER_DOMAIN" "$AGENT_ROOT/$name"
  fi
done

echo "Previous HomeSentinel launch agents restored from: $BACKUP_ROOT"
echo "The copied runtime was retained at $RUNTIME_ROOT for recovery or inspection."
