#!/bin/bash
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_ROOT="$HOME/Library/Application Support/HomeSentinel"
APP_ROOT="$RUNTIME_ROOT/app"
DATA_ROOT="$RUNTIME_ROOT/data"
DATABASE_PATH="$RUNTIME_ROOT/data/homesentinel.db"
LOG_ROOT="$HOME/Library/Logs/HomeSentinel"
AGENT_ROOT="$HOME/Library/LaunchAgents"
BACKUP_ROOT="$RUNTIME_ROOT/plist-backups/$(date +%Y%m%d-%H%M%S)"
BACKEND_LABEL="com.homesentinel.backend"
FRONTEND_LABEL="com.homesentinel.frontend"
BACKEND_PLIST="$AGENT_ROOT/$BACKEND_LABEL.plist"
FRONTEND_PLIST="$AGENT_ROOT/$FRONTEND_LABEL.plist"
USER_DOMAIN="gui/$(id -u)"

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3)}"
NODE_BIN="${NODE_BIN:-$(command -v node)}"

mkdir -p "$APP_ROOT" "$DATA_ROOT" "$LOG_ROOT" "$AGENT_ROOT" "$BACKUP_ROOT"

for plist in "$BACKEND_PLIST" "$FRONTEND_PLIST"; do
  if [ -f "$plist" ]; then
    cp -p "$plist" "$BACKUP_ROOT/"
  fi
done
printf '%s\n' "$BACKUP_ROOT" > "$RUNTIME_ROOT/latest-plist-backup"

rsync -a --delete \
  --exclude='.git/' \
  --exclude='.venv*/' \
  --exclude='node_modules/' \
  --exclude='backend/homesentinel.db*' \
  --exclude='backend/logs/' \
  --exclude='frontend/build/' \
  "$SOURCE_ROOT/" "$APP_ROOT/"

if [ ! -f "$DATABASE_PATH" ] && [ -f "$SOURCE_ROOT/backend/homesentinel.db" ]; then
  cp -p "$SOURCE_ROOT/backend/homesentinel.db" "$DATABASE_PATH"
fi

if [ ! -x "$RUNTIME_ROOT/venv/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$RUNTIME_ROOT/venv"
fi
"$RUNTIME_ROOT/venv/bin/python" -m pip install -r "$APP_ROOT/backend/requirements.txt"
(cd "$APP_ROOT/frontend" && "$NODE_BIN" "$(dirname "$NODE_BIN")/npm" ci)

cat > "$BACKEND_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$BACKEND_LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$RUNTIME_ROOT/venv/bin/python</string>
    <string>$APP_ROOT/backend/main.py</string>
  </array>
  <key>WorkingDirectory</key><string>$APP_ROOT/backend</string>
  <key>EnvironmentVariables</key><dict>
    <key>DB_PATH</key><string>$DATABASE_PATH</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG_ROOT/backend.stdout.log</string>
  <key>StandardErrorPath</key><string>$LOG_ROOT/backend.stderr.log</string>
</dict></plist>
EOF

cat > "$FRONTEND_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$FRONTEND_LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$NODE_BIN</string>
    <string>$APP_ROOT/frontend/node_modules/vite/bin/vite.js</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>2026</string>
  </array>
  <key>WorkingDirectory</key><string>$APP_ROOT/frontend</string>
  <key>EnvironmentVariables</key><dict>
    <key>NODE_ENV</key><string>production</string>
    <key>PATH</key><string>$(dirname "$NODE_BIN"):/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG_ROOT/frontend.stdout.log</string>
  <key>StandardErrorPath</key><string>$LOG_ROOT/frontend.stderr.log</string>
</dict></plist>
EOF

plutil -lint "$BACKEND_PLIST" "$FRONTEND_PLIST"
launchctl bootout "$USER_DOMAIN/$BACKEND_LABEL" 2>/dev/null || true
launchctl bootout "$USER_DOMAIN/$FRONTEND_LABEL" 2>/dev/null || true
launchctl bootstrap "$USER_DOMAIN" "$BACKEND_PLIST"
launchctl bootstrap "$USER_DOMAIN" "$FRONTEND_PLIST"

echo "HomeSentinel runtime installed at: $RUNTIME_ROOT"
echo "Previous launch agents backed up at: $BACKUP_ROOT"
echo "Rollback with: $SOURCE_ROOT/scripts/rollback-macos-runtime.sh"
