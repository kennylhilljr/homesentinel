# HomeSentinel

A comprehensive smart home security monitoring system that integrates with Deco/Alexa devices to provide real-time alerts, logs, and intelligent automation.

## Overview

HomeSentinel is an intelligent home security platform that monitors smart home devices, detects unusual activity, logs security events, and triggers automated responses. The system provides both a web dashboard and voice-controlled interface through Alexa integration.

## Technology Stack

### Backend
- **Runtime**: Python 3.9+
- **Framework**: FastAPI with HTTPS support
- **Database**: SQLite (development)
- **Authentication**: OAuth2, device token-based auth
- **Integration**: Deco/Alexa SDK, HomeKit Accessory Protocol

### Frontend
- **Framework**: React.js
- **Build Tool**: webpack/Vite
- **Styling**: CSS/Tailwind CSS
- **State Management**: Redux or Context API
- **UI Components**: Custom responsive components

### Infrastructure
- **Dev Server**: Node.js + webpack/Vite
- **HTTPS**: SSL certificates for secure communication
- **Containerization**: Docker support
- **CI/CD**: GitHub Actions (optional)

## Quick Start

### Prerequisites
- Python 3.9 or higher
- Node.js 14+ and npm
- OpenSSL (for HTTPS certificates)

### Installation & Running

1. Clone the repository:
```bash
git clone <repository-url>
cd homesentinel
```

2. Run the initialization script:
```bash
chmod +x init.sh
./init.sh
```

This will:
- Install Python dependencies
- Install Node.js dependencies
- Start the backend server (HTTPS on localhost:8443)
- Start the frontend dev server (localhost:3000)

### Manual Setup (if preferred)

**Backend Setup:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start backend server
python backend/main.py
# Server runs on https://localhost:8443
```

**Frontend Setup:**
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm start
# Dev server runs on http://localhost:3000
```

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────┐
│                   Web Dashboard                      │
│              (React - localhost:3000)                │
└────────────────┬────────────────────────────────────┘
                 │
                 │ REST API / WebSocket
                 │
┌────────────────▼────────────────────────────────────┐
│              FastAPI Backend                        │
│          (HTTPS - localhost:8443)                   │
│                                                      │
│  - Device Management & Monitoring                   │
│  - Event Logging & Analytics                        │
│  - Alert Orchestration                              │
│  - Authentication & Authorization                   │
└────────────┬─────────────┬──────────────┬───────────┘
             │             │              │
      ┌──────▼─┐    ┌──────▼──┐    ┌─────▼──────┐
      │  Deco  │    │  Alexa  │    │  HomeKit   │
      │  API   │    │   SDK   │    │  Protocol  │
      └────────┘    └─────────┘    └────────────┘
```

### Key Features
- **Device Integration**: Connect and monitor Deco mesh routers, Alexa devices, and HomeKit accessories
- **Event Management**: Real-time event detection and logging
- **Alert System**: Configurable alerts with multiple notification channels
- **Dashboard**: Real-time visualization of device status and security events
- **Automation**: Trigger actions based on security events
- **Voice Control**: Alexa integration for voice-based commands

## Setup Guide for Deco/Alexa Credentials

### 1. Deco API Setup

1. Create a TP-Link account at https://www.tplink.com/
2. Enable Developer Mode and generate API credentials
3. Create `.env` file with:
```env
DECO_CLIENT_ID=your_client_id
DECO_CLIENT_SECRET=your_client_secret
DECO_USERNAME=your_tp_link_username
DECO_PASSWORD=your_tp_link_password
```

### 2. Alexa Integration Setup

1. Create an Amazon Developer Account at https://developer.amazon.com/
2. Create a new Alexa Smart Home Skill
3. Configure OAuth2 endpoint and obtain:
   - Client ID
   - Client Secret
   - Refresh Token
4. Add to `.env`:
```env
ALEXA_CLIENT_ID=your_alexa_client_id
ALEXA_CLIENT_SECRET=your_alexa_client_secret
ALEXA_REFRESH_TOKEN=your_refresh_token
ALEXA_ENDPOINT=https://api.amazonalexa.com
```

### 3. HTTPS Certificate Setup

The backend uses self-signed certificates for development. They are generated automatically on first run.

For production, use proper SSL certificates:
```bash
# Backend will look for certificates in ./backend/certs/
# Create proper certs and place them there
```

### 4. Environment Variables

Create a `.env.local` file in the frontend directory for frontend-specific configuration:
```env
REACT_APP_API_URL=https://localhost:8443
REACT_APP_WS_URL=wss://localhost:8443
```

## Project Structure

```
homesentinel/
├── backend/
│   ├── main.py              # FastAPI application entry point
│   ├── requirements.txt      # Python dependencies
│   ├── api/                 # API routes
│   ├── models/              # Data models
│   ├── services/            # Business logic
│   ├── integrations/        # Deco, Alexa, HomeKit integration
│   ├── certs/               # SSL certificates
│   └── logs/                # Application logs
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API service layer
│   │   ├── utils/           # Utility functions
│   │   └── App.js           # Main app component
│   ├── public/              # Static assets
│   ├── package.json         # Node dependencies
│   └── webpack.config.js    # Webpack configuration
├── init.sh                  # Project initialization script
├── README.md                # This file
├── .gitignore               # Git ignore patterns
└── app_spec.txt             # Detailed specifications
```

## Development

### Running Tests
```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd ../frontend
npm test
```

### Building for Production
```bash
# Frontend build
cd frontend
npm run build

# Backend is ready to run as-is
python backend/main.py
```

## Stopping Services

To stop the running services:
1. Press `Ctrl+C` in the terminal where init.sh is running
2. Or in separate terminals:
   - Press `Ctrl+C` to stop each service individually
   - Services will gracefully shutdown

## Troubleshooting

### Port Already in Use
- Frontend (3000): `lsof -ti:3000 | xargs kill -9`
- Backend (8443): `lsof -ti:8443 | xargs kill -9`

### Certificate Issues
Delete existing certificates and they'll be regenerated:
```bash
rm -rf backend/certs/
```

### Dependency Issues
Reinstall all dependencies:
```bash
./init.sh clean
./init.sh
```

## License

Proprietary - HomeSentinel Project

## Support

For issues, questions, or feature requests, please contact the development team.
