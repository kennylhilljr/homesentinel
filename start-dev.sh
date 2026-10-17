#!/bin/bash
# Start both backend and frontend servers

echo "Starting HomeSentinel Development Servers..."

NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    . "$NVM_DIR/nvm.sh"
    nvm use --lts >/dev/null 2>&1 || nvm use node >/dev/null 2>&1 || true
fi

# Install backend dependencies
echo "Installing backend dependencies..."
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
    for candidate in python3.12 python3.11 python3.10 python3.9 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "No Python 3 interpreter found."
    exit 1
fi

if [ -x backend/.venv/bin/python ]; then
    if ! backend/.venv/bin/python - <<'PY'
import sys
major, minor = sys.version_info[:2]
raise SystemExit(0 if major == 3 and 9 <= minor <= 12 else 1)
PY
    then
        mv backend/.venv "backend/.venv.$(date +%s).bak"
    fi
fi

if [ ! -x backend/.venv/bin/python ]; then
    "$PYTHON_BIN" -m venv backend/.venv
fi

backend/.venv/bin/python -m pip install -r backend/requirements.txt

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend && npm install 2>/dev/null
cd ..

# Start backend in background
echo "Starting backend server (localhost:8443)..."
backend/.venv/bin/python backend/main.py &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend
echo "Starting frontend dev server (localhost:2026)..."
cd frontend && npm start &
FRONTEND_PID=$!

echo "Both servers are starting..."
echo "Frontend: http://localhost:2026"
echo "Backend: https://localhost:8443"
echo ""
echo "Press Ctrl+C to stop all services"

wait
