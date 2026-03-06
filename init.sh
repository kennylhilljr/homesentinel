#\!/bin/bash
echo "HomeSentinel initialization script"
mkdir -p backend/logs backend/certs frontend/src/components frontend/src/pages
echo "Setup complete\!"
python3 -m pip install -r backend/requirements.txt 2>/dev/null || true
npm install --prefix frontend 2>/dev/null || true
mkdir -p backend/certs
cd backend/certs && openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj "/C=US/ST=State/L=City/O=HomeSentinel/CN=localhost" 2>/dev/null
