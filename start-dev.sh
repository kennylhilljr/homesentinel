#!/bin/bash
# Start both backend and frontend servers

echo "Starting HomeSentinel Development Servers..."

# Install backend dependencies
echo "Installing backend dependencies..."
pip install -r backend/requirements.txt 2>/dev/null || pip3 install -r backend/requirements.txt

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend && npm install 2>/dev/null
cd ..

# Start backend in background
echo "Starting backend server (localhost:8443)..."
python3 backend/main.py &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend
echo "Starting frontend dev server (localhost:3000)..."
cd frontend && npm start &
FRONTEND_PID=$!

echo "Both servers are starting..."
echo "Frontend: http://localhost:3000"
echo "Backend: https://localhost:8443"
echo ""
echo "Press Ctrl+C to stop all services"

wait
