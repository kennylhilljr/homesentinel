#!/bin/bash
# HomeSentinel service controller
# Usage: homesentinel-ctl.sh [status|start|stop|restart]

BACKEND_LABEL="com.homesentinel.backend"
FRONTEND_LABEL="com.homesentinel.frontend"
BACKEND_PLIST="$HOME/Library/LaunchAgents/$BACKEND_LABEL.plist"
FRONTEND_PLIST="$HOME/Library/LaunchAgents/$FRONTEND_LABEL.plist"

check_backend() {
    curl -sk https://localhost:8443/api/health -o /dev/null -w "%{http_code}" 2>/dev/null
}

check_frontend() {
    curl -s http://localhost:2026 -o /dev/null -w "%{http_code}" 2>/dev/null
}

status() {
    echo "=== HomeSentinel Status ==="

    local be_http=$(check_backend)
    local be_pid=$(lsof -ti:8443 2>/dev/null)
    if [ "$be_http" = "200" ]; then
        echo "Backend:  ✓ running (PID $be_pid, port 8443)"
    else
        echo "Backend:  ✗ down"
    fi

    local fe_http=$(check_frontend)
    local fe_pid=$(lsof -ti:2026 2>/dev/null)
    if [ "$fe_http" = "200" ]; then
        echo "Frontend: ✓ running (PID $fe_pid, port 2026)"
    else
        echo "Frontend: ✗ down"
    fi

    local be_loaded=$(launchctl list | grep -c "$BACKEND_LABEL")
    local fe_loaded=$(launchctl list | grep -c "$FRONTEND_LABEL")
    echo ""
    echo "LaunchAgents:"
    echo "  Backend:  $([ "$be_loaded" -gt 0 ] && echo '✓ loaded' || echo '✗ not loaded')"
    echo "  Frontend: $([ "$fe_loaded" -gt 0 ] && echo '✓ loaded' || echo '✗ not loaded')"
}

start() {
    echo "Starting HomeSentinel..."

    if ! launchctl list | grep -q "$BACKEND_LABEL"; then
        launchctl load "$BACKEND_PLIST" 2>/dev/null
    else
        launchctl start "$BACKEND_LABEL"
    fi

    if ! launchctl list | grep -q "$FRONTEND_LABEL"; then
        launchctl load "$FRONTEND_PLIST" 2>/dev/null
    else
        launchctl start "$FRONTEND_LABEL"
    fi

    echo "Waiting for services..."
    for i in $(seq 1 30); do
        [ "$(check_backend)" = "200" ] && [ "$(check_frontend)" = "200" ] && break
        sleep 2
    done
    status
}

stop() {
    echo "Stopping HomeSentinel..."
    launchctl stop "$BACKEND_LABEL" 2>/dev/null
    launchctl stop "$FRONTEND_LABEL" 2>/dev/null
    sleep 1
    status
}

restart() {
    stop
    sleep 2
    start
}

case "${1:-status}" in
    status)  status ;;
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    *)       echo "Usage: $0 [status|start|stop|restart]" ;;
esac
