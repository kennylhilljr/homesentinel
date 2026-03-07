# HomeSentinel Architecture Documentation

## System Overview

HomeSentinel is a smart home security monitoring platform built with a modern, scalable architecture. The system is designed as a distributed application with clear separation of concerns between frontend and backend layers.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                             │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Web Dashboard (React)                          │  │
│  │         Running on localhost:3000                      │  │
│  │                                                         │  │
│  │  - Components: Header, StatusCard, DeviceList, etc    │  │
│  │  - State Management: React Hooks (useState, useEffect) │  │
│  │  - API Client: Fetch API with error handling          │  │
│  │  - Styling: CSS with responsive design               │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTPS REST API / WebSocket
                     │ Port 8443
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  Backend API Layer                           │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         FastAPI Application                           │  │
│  │         Running on localhost:8443 (HTTPS)             │  │
│  │                                                         │  │
│  │  Endpoints:                                            │  │
│  │  - GET  /                (Root health check)          │  │
│  │  - GET  /api/health      (API health status)          │  │
│  │  - GET  /api/devices     (List discovered devices)    │  │
│  │                                                         │  │
│  │  Middleware:                                           │  │
│  │  - CORS Configuration (Allow localhost:3000)          │  │
│  │  - HTTPS/SSL Support                                  │  │
│  │  - Request/Response Logging                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Data & Integration Layer (Future)             │  │
│  │                                                         │  │
│  │  - Device Management Service                          │  │
│  │  - Event Logging System                               │  │
│  │  - Alert Orchestration                                │  │
│  │  - Authentication & Authorization                     │  │
│  │  - Data Models & Validators                           │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────┬───┬──────────────────┬──────────────────┘
                     │   │                  │
                     │   │                  │
        ┌────────────▼┐  │         ┌────────▼────────┐
        │    Deco     │  │         │     Alexa       │
        │   Router    │  │         │    Integration  │
        │  Integration│  │         │                 │
        └─────────────┘  │         └─────────────────┘
                         │
                    ┌────▼─────────┐
                    │   HomeKit     │
                    │  Accessories  │
                    └───────────────┘
```

## Core Components

### Frontend (React)

**Location**: `/frontend`

**Key Features**:
- Single Page Application (SPA) built with React 18
- Real-time status monitoring with polling mechanism
- Responsive UI design using CSS
- Error handling and user-friendly messaging
- WebSocket-ready architecture (for future enhancements)

**Component Structure**:
```
src/
├── App.js              # Main application component
├── App.css             # Application styling
├── components/         # Reusable UI components
├── pages/             # Page-level components
├── services/          # API communication layer
├── utils/             # Helper functions
└── index.js           # React DOM rendering
```

**Development Stack**:
- Framework: React 18.2.0
- Build Tool: Create React App (react-scripts)
- HTTP Client: Fetch API (built-in)
- Testing: Jest + React Testing Library

### Backend (FastAPI)

**Location**: `/backend`

**Key Features**:
- RESTful API built with FastAPI
- HTTPS/SSL support for secure communication
- CORS middleware for cross-origin requests
- Asynchronous request handling
- Automatic API documentation (Swagger/OpenAPI)

**Current Endpoints**:
```
GET  /               - Root health check
GET  /api/health     - API health status
GET  /api/devices    - List discovered devices
```

**Development Stack**:
- Framework: FastAPI 0.104.1
- Server: Uvicorn 0.24.0
- Data Validation: Pydantic 2.4.2
- Testing: pytest 7.4.3, pytest-cov 4.1.0

**Middleware Configuration**:
- CORS: Allows http://localhost:3000 and https://localhost:3000
- SSL/TLS: Self-signed certificates for development

### SSL/HTTPS Configuration

**Certificate Location**: `/backend/certs/`

**Files**:
- `cert.pem`: Self-signed certificate
- `key.pem`: Private key

**Auto-Generation**: Certificates are automatically generated on first run if they don't exist.

**For Production**: Replace self-signed certs with valid SSL certificates from a trusted CA.

## Data Flow

### Initial Application Load

1. User navigates to `http://localhost:3000`
2. React App mounts and executes `useEffect` hook
3. App sends GET request to `https://localhost:8443/api/health`
4. App sends GET request to `https://localhost:8443/api/devices`
5. Responses are processed and state is updated
6. UI renders with current status and device list
7. Component sets up interval for periodic health checks (5 seconds)

### API Communication

**Request Format**:
```javascript
fetch('https://localhost:8443/api/health', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
  },
})
```

**Response Format**:
```json
{
  "status": "healthy",
  "service": "HomeSentinel Backend"
}
```

## Development Workflow

### Local Development Setup

1. **Dependencies Installation**:
   ```bash
   ./init.sh  # Installs all dependencies
   ```

2. **Development Servers**:
   - Frontend Dev Server: `npm start` (port 3000)
   - Backend API Server: `python backend/main.py` (port 8443)

3. **Testing**:
   - Backend Tests: `pytest tests/ -v --cov=. --cov-report=term`
   - Frontend Tests: `npm test -- --coverage --watchAll=false`

4. **Building for Production**:
   - Frontend Build: `npm run build`
   - Backend: Runs as-is (no build required)

## Security Considerations

1. **HTTPS/SSL**: All backend communication is encrypted
2. **CORS Policy**: Restricted to localhost development addresses
3. **Environment Variables**: Sensitive data stored in `.env` (not in version control)
4. **Input Validation**: Pydantic models validate all API input

## Error Handling

### Frontend Error Handling

- Try/catch blocks for API calls
- Graceful degradation with user-friendly messages
- Console error logging for debugging
- State management for error states

### Backend Error Handling

- FastAPI automatic validation errors (400 responses)
- CORS middleware error handling
- Proper HTTP status codes
- Structured error responses

## Scalability & Future Enhancements

### Planned Components

1. **Authentication System**:
   - OAuth2 integration
   - JWT token-based auth
   - User session management

2. **Device Management**:
   - Device discovery and registration
   - Device health monitoring
   - Device-specific configurations

3. **Event System**:
   - Real-time event logging
   - Event filtering and search
   - Event analytics

4. **Alert System**:
   - Configurable alert rules
   - Multi-channel notifications
   - Alert history and management

5. **Third-Party Integrations**:
   - Deco Router API integration
   - Alexa Smart Home Skills
   - HomeKit Accessory Protocol

6. **Database Layer**:
   - SQLite for development
   - PostgreSQL for production
   - ORM for data access (SQLAlchemy)

7. **WebSocket Support**:
   - Real-time status updates
   - Live notifications
   - Bidirectional communication

## Testing Architecture

### Test Pyramid

```
           /\
          /  \  API Integration Tests
         /    \
        /______\
       /        \
      / Backend  \ Endpoint Tests
     /  Unit      \
    /______________\
   /                \
  /  Frontend Unit   \ Component Tests
 /  Component Tests   \
/_____________________\
```

### Test Categories

1. **Unit Tests**: Individual component/function testing
2. **Integration Tests**: API and cross-layer communication
3. **End-to-End Tests**: Full application workflow

## Performance Optimization

1. **Frontend**:
   - Lazy loading of components
   - Efficient state management
   - CSS optimization

2. **Backend**:
   - Async/await for non-blocking I/O
   - Connection pooling for databases
   - Caching mechanisms

3. **Network**:
   - HTTPS/HTTP/2 support
   - Request compression
   - Smart polling intervals

## Deployment Architecture (Future)

```
┌─────────────────────────────────────────┐
│       Docker Containers                 │
│                                          │
│  ┌──────────────────┐  ┌─────────────┐ │
│  │  Frontend (Nginx) │  │ Backend     │ │
│  │  Port: 80/443    │  │ (Gunicorn)  │ │
│  │                  │  │ Port: 8443  │ │
│  └────────┬─────────┘  └──────┬──────┘ │
│           │                    │        │
│           └────────┬───────────┘        │
│                    │                    │
└────────────────────┼───────────────────┘
                     │
          ┌──────────▼──────────┐
          │  PostgreSQL DB      │
          │  Redis Cache        │
          │  File Storage       │
          └─────────────────────┘
```

## Configuration Management

### Environment Variables

- **Development**: `.env.development`
- **Production**: `.env` (not in git)
- **Example**: `.env.example` (template)

### Key Configuration Areas

1. **API URLs**: Backend endpoint configuration
2. **Ports**: Server port assignments
3. **Database**: Connection strings
4. **External Services**: API keys and credentials
5. **Logging**: Log levels and formats

## Monitoring & Logging

### Logging Strategy

1. **Backend**: Python logging with configurable levels
2. **Frontend**: Console logging with error tracking
3. **Application**: Request/response logging

### Monitoring Points

- API health checks
- Response times
- Error rates
- Device status
- System resources

## Conclusion

HomeSentinel's architecture provides a solid foundation for a modern smart home security platform. The separation of concerns between frontend and backend enables independent scaling and development. The modular design allows for easy integration of new features and third-party services as the project evolves.
