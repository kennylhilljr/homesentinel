# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

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

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
