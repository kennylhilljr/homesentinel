# HomeSentinel API Documentation

## Base URL

```
https://localhost:8443
```

## Authentication

Currently, no authentication is required for development endpoints. Authentication will be added in future versions using OAuth2/JWT.

## Response Format

All API responses are in JSON format.

### Success Response Format

```json
{
  "status": "ok",
  "data": {}
}
```

### Error Response Format

```json
{
  "detail": "Error message describing the issue"
}
```

## HTTP Status Codes

- `200 OK`: Request succeeded
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `405 Method Not Allowed`: HTTP method not allowed for endpoint
- `500 Internal Server Error`: Server error

## Endpoints

### 1. Root Health Check

Get basic health status of the API.

**Endpoint**: `GET /`

**Description**: Health check endpoint for API availability verification.

**Request**:
```bash
curl -k https://localhost:8443/
```

**Response** (200 OK):
```json
{
  "status": "ok",
  "message": "HomeSentinel API is running",
  "version": "1.0.0"
}
```

**Use Cases**:
- Verify API is running
- Check API version
- General health monitoring

---

### 2. API Health Status

Get detailed health information about the API service.

**Endpoint**: `GET /api/health`

**Description**: Returns current health status of the HomeSentinel Backend service.

**Request**:
```bash
curl -k https://localhost:8443/api/health
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "service": "HomeSentinel Backend"
}
```

**Status Values**:
- `healthy`: Service is operating normally
- `degraded`: Service is running but experiencing issues
- `unhealthy`: Service is not functioning properly

**Use Cases**:
- Frontend periodic health checks
- Load balancer health verification
- Service status monitoring

---

### 3. Get Devices

Get list of all discovered network devices.

**Endpoint**: `GET /api/devices`

**Description**: Returns a list of all devices discovered on the monitored network.

**Request**:
```bash
curl -k https://localhost:8443/api/devices
```

**Query Parameters** (Optional - Future Implementation):
- `skip` (int): Number of records to skip (pagination)
- `limit` (int): Maximum number of records to return
- `type` (string): Filter by device type (router, camera, etc.)
- `status` (string): Filter by device status (online, offline, etc.)

**Response** (200 OK):
```json
{
  "devices": [
    {
      "id": "device-001",
      "name": "Living Room Router",
      "mac_address": "00:11:22:33:44:55",
      "type": "router",
      "status": "online",
      "ip_address": "192.168.1.1",
      "last_seen": "2025-03-06T12:34:56Z"
    },
    {
      "id": "device-002",
      "name": "Front Door Camera",
      "mac_address": "00:11:22:33:44:66",
      "type": "camera",
      "status": "online",
      "ip_address": "192.168.1.10",
      "last_seen": "2025-03-06T12:34:50Z"
    }
  ],
  "total": 2
}
```

**Current Response** (Development):
```json
{
  "devices": [],
  "total": 0
}
```

**Device Object Fields**:
- `id` (string): Unique device identifier
- `name` (string): Human-readable device name
- `mac_address` (string): MAC address of the device
- `type` (string): Device type (router, camera, sensor, etc.)
- `status` (string): Current device status (online/offline)
- `ip_address` (string): IP address (if available)
- `last_seen` (string): ISO 8601 timestamp of last activity

**Use Cases**:
- Display list of network devices
- Monitor device availability
- Device status tracking
- Network inventory management

---

## Request Headers

### Required Headers

```
Content-Type: application/json
```

### Optional Headers

```
Authorization: Bearer <token>  (Future implementation)
```

## CORS Policy

### Allowed Origins
- `http://localhost:3000`
- `https://localhost:3000`

### Allowed Methods
- GET
- POST
- PUT
- DELETE
- OPTIONS
- PATCH

### Allowed Headers
- Content-Type
- Authorization (Future)

### Credentials
- Allowed: true

## Examples

### JavaScript/Fetch

**Health Check**:
```javascript
fetch('https://localhost:8443/api/health', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
  },
})
.then(response => response.json())
.then(data => console.log('Health:', data))
.catch(error => console.error('Error:', error));
```

**Get Devices**:
```javascript
fetch('https://localhost:8443/api/devices', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
  },
})
.then(response => response.json())
.then(data => {
  console.log('Devices:', data.devices);
  console.log('Total:', data.total);
})
.catch(error => console.error('Error:', error));
```

### Python

**Health Check**:
```python
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for development
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

response = requests.get(
    'https://localhost:8443/api/health',
    verify=False
)
print(response.json())
```

**Get Devices**:
```python
import requests

response = requests.get(
    'https://localhost:8443/api/devices',
    verify=False
)
data = response.json()
print(f"Total devices: {data['total']}")
for device in data['devices']:
    print(f"  - {device['name']} ({device['mac_address']})")
```

### cURL

**Health Check**:
```bash
curl -k https://localhost:8443/api/health
```

**Get Devices**:
```bash
curl -k https://localhost:8443/api/devices
```

### Axios

**Health Check**:
```javascript
import axios from 'axios';

axios.get('https://localhost:8443/api/health', {
  httpsAgent: new (require('https').Agent)({ rejectUnauthorized: false })
})
.then(response => console.log(response.data))
.catch(error => console.error(error));
```

## Error Handling

### Common Errors

**404 Not Found**:
```json
{
  "detail": "Not Found"
}
```

**405 Method Not Allowed**:
```json
{
  "detail": "Method Not Allowed"
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Internal Server Error"
}
```

## Rate Limiting

Currently, there is no rate limiting on API endpoints. This will be implemented in future versions.

## Future Endpoints (Planned)

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `POST /api/auth/refresh` - Refresh authentication token

### Device Management
- `POST /api/devices` - Register new device
- `PUT /api/devices/{id}` - Update device information
- `DELETE /api/devices/{id}` - Remove device
- `GET /api/devices/{id}` - Get specific device details

### Events & Alerts
- `GET /api/events` - Get security events
- `GET /api/alerts` - Get alerts
- `POST /api/alerts` - Create alert rule

### System
- `GET /api/system/config` - Get system configuration
- `PUT /api/system/config` - Update system configuration
- `GET /api/system/logs` - Get system logs

## API Versioning

Current API Version: `1.0.0`

Future versions will be available at:
- `https://localhost:8443/api/v1/health`
- `https://localhost:8443/api/v2/health`

## Testing the API

### Automated Testing

Run the backend test suite:
```bash
cd backend
pytest tests/ -v --cov=. --cov-report=term
```

### Manual Testing

Start the development servers:
```bash
./init.sh
```

Then test endpoints using curl, Postman, or your browser's developer console.

## SSL/TLS Certificate

For development, self-signed certificates are automatically generated. To test with curl:

```bash
curl -k https://localhost:8443/api/health
```

The `-k` flag ignores certificate verification warnings (development only).

## WebSocket Support (Future)

WebSocket connections for real-time updates will be available at:
```
wss://localhost:8443/ws/events
```

## Pagination (Future Implementation)

When pagination is implemented, use these query parameters:

```bash
GET /api/devices?skip=0&limit=10
```

## Filtering (Future Implementation)

Filter devices by type and status:

```bash
GET /api/devices?type=camera&status=online
```

## Sorting (Future Implementation)

Sort devices by last activity:

```bash
GET /api/devices?sort_by=last_seen&order=desc
```

## Support & Issues

For API issues or feature requests, please refer to the project repository or contact the development team.

## Changelog

### Version 1.0.0 (March 2025)

**Initial Release**:
- Root health check endpoint
- API health status endpoint
- Devices list endpoint
- CORS support for frontend integration
- HTTPS/SSL support

---

## API Status

**Current Status**: Beta (Development Phase)

**Production Ready**: No

The API is currently in development phase with basic endpoints for health monitoring and device discovery. Full production release is planned for Q2 2025.
