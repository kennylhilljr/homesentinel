#!/bin/bash
set -euo pipefail

SERVICE="${1:-}"
ACTION="${2:-}"
USER_DOMAIN="gui/$(id -u)"

case "$SERVICE" in
  backend|frontend) LABEL="com.homesentinel.$SERVICE" ;;
  *) echo "Service is not allowlisted" >&2; exit 64 ;;
esac

case "$ACTION" in
  restart|stop) ;;
  *) echo "Action is not allowlisted" >&2; exit 64 ;;
esac

if [ "$ACTION" = "restart" ]; then
  launchctl kickstart -k "$USER_DOMAIN/$LABEL"
else
  # Return the HTTP response before stopping the service that handled it.
  (
    sleep 1
    launchctl bootout "$USER_DOMAIN/$LABEL" 2>/dev/null || true
  ) >/dev/null 2>&1 &
fi
