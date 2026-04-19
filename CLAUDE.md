# HomeSentinel

Home network monitoring and smart home management platform.

## Quick Commands

```bash
./init.sh                          # Full setup (deps + certs + start)
./start-dev.sh                     # Start backend + frontend
cd backend && python main.py       # Backend only (HTTPS :8443)
cd frontend && npm start           # Frontend only (:2026)
cd backend && pytest -v            # Run tests
docker compose up -d               # Docker deployment
```

## File Map

| Path | Purpose |
|------|---------|
| `backend/main.py` | FastAPI entry point — routes, startup/shutdown, CORS, SPA catch-all |
| `backend/db.py` | SQLite connection, WAL mode, write locking, migration runner |
| `backend/utils.py` | MAC normalization, Fernet credential encryption/decryption |
| `backend/routes/` | 12 API route modules (deco, chester, alexa, hiboost, alarm_com, etc.) |
| `backend/services/` | 23 service files (clients, scanners, schedulers) |
| `backend/middleware/auth.py` | API key auth middleware (`X-API-Key` header) |
| `backend/migrations/` | 16 sequential SQL migrations (001–016) |
| `backend/tests/` | 20 pytest test files |
| `frontend/src/App.jsx` | Main React app — theme, nav, lazy page mounting |
| `frontend/src/hooks/useDevicePolling.js` | Central data hook — SSE + multi-tier polling |
| `frontend/src/components/` | 34+ React components |
| `frontend/src/pages/` | 11 page components |
| `lambda/lambda_function.py` | Alexa Smart Home Skill v3 (AWS Lambda) |

## Architecture

```
FastAPI Backend (HTTPS :8443)
├── Routes (12 modules)
│   ├── devices, events, settings, sse, digest, health, oauth
│   └── deco, chester, alexa, hiboost, alarm_com, speedtest
├── Services (23 modules)
│   ├── Device Scanner (ARP scan + Deco merge)
│   ├── Integration Clients (Deco, Chester, Alexa, HiBoost, Alarm.com)
│   ├── Background Schedulers (polling, speedtest, hiboost, retention)
│   └── Analytics (correlation, OUI lookup, health score, digest)
├── SQLite (WAL mode, 16 migrations, threading.Lock for writes)
└── Fernet Encryption (credentials at rest)

React Frontend (:2026)
├── useDevicePolling hook (SSE + 15s/30s/60s polling tiers)
├── 11 Pages (Dashboard, Topology, Alexa, SmartHome, Speed, HiBoost, Settings, ...)
└── 34+ Components (DeviceTable, DecoTopologyView, CellularCard, ...)
```

## Route Prefixes

| Prefix | File | Description |
|--------|------|-------------|
| `/api/devices` | `main.py` | Device CRUD, search, scan-now |
| `/api/events` | `main.py` + `routes/events.py` | Events, alerts, stats |
| `/api/deco` | `routes/deco.py` | Mesh nodes, topology, WiFi, QoS |
| `/api/chester` | `routes/chester.py` | 5G router status, cellular signal |
| `/api/alexa` | `routes/alexa.py` | Alexa devices, state, control |
| `/api/hiboost` | `routes/hiboost.py` | Signal booster RF parameters |
| `/api/alarm-com` | `routes/alarm_com.py` | Partitions, sensors, locks |
| `/api/speedtest` | `routes/speedtest.py` | Speed test execution + history |
| `/api/settings` | `routes/settings.py` | Credential management |
| `/api/sse` | `routes/sse.py` | Server-Sent Events stream |
| `/api/digest` | `routes/digest.py` | Daily network digest |
| `/api/network` | `routes/health.py` | Health score (0-100) |
| `/oauth` | `routes/oauth.py` | Alexa account linking OAuth |

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_PORT` | `8443` | HTTPS port |
| `NETWORK_SUBNET` | `192.168.12.0/24` | ARP scan subnet |
| `POLLING_INTERVAL_SECONDS` | `60` | Device scan interval |
| `HOMESENTINEL_API_KEY` | _(empty)_ | API key (empty = auth disabled) |
| `CREDENTIAL_KEY` | _(auto-gen)_ | Fernet encryption key |
| `OAUTH_CLIENT_SECRET` | _(required)_ | OAuth secret for Alexa |
| `SPEEDTEST_INTERVAL_SECONDS` | `1800` | Speed test interval |
| `HIBOOST_POLL_INTERVAL` | `300` | HiBoost RF poll interval |
| `RETENTION_DAYS` | `90` | Event data retention |

## Database

- **Engine**: SQLite with WAL journal mode
- **Write safety**: `threading.Lock` serializes all writes (avoids "database locked")
- **Migrations**: Sequential SQL files in `backend/migrations/` (001–016)
- **Credentials**: Encrypted at rest with Fernet; key from `CREDENTIAL_KEY` env var or auto-generated `.credential_key` file

## Key Patterns

### Startup wiring

All services are initialized in `main.py:startup_event()` and stored as module-level globals. Route modules receive service instances via setter functions (e.g., `deco_routes.set_deco_service(deco_service)`).

### Credential storage

```python
from utils import store_encrypted_setting, load_encrypted_setting
# Store: JSON dict -> Fernet encrypt -> app_settings table
store_encrypted_setting(conn, "deco_credentials", {"username": "...", "password": "..."})
# Load: app_settings -> Fernet decrypt -> JSON dict (falls back to plain JSON for compat)
creds = load_encrypted_setting(conn, "deco_credentials")
```

### SSE real-time updates

The frontend uses `EventSource` to receive device updates pushed from the backend. The `useDevicePolling` hook manages SSE alongside multi-tier polling (15s for active, 30s for moderate, 60s for background data).

### Frontend page mounting

Pages use lazy-mount: first visit adds the page to `mountedPages` Set, then it stays in the DOM (hidden via `display: none`) to avoid refetching data on tab switches.
