"""
HomeSentinel Alexa Smart Home Lambda Handler

Full Alexa Smart Home Skill API v3 implementation for home network monitoring.
Handles device discovery, state reporting, and control directives for:
  - Deco mesh nodes (health, reboot)
  - Deco WiFi networks (guest WiFi, IoT network toggle)
  - Chester 5G router (health, signal status)
  - Connected network clients (presence detection)

Environment variables:
  HOMESENTINEL_URL: Backend URL (e.g. https://charissa-nonrefractional-dwana.ngrok-free.dev)
  HOMESENTINEL_API_KEY: Optional API key for backend auth
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from urllib import request, error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

HOMESENTINEL_URL = os.environ.get("HOMESENTINEL_URL", "")
HOMESENTINEL_API_KEY = os.environ.get("HOMESENTINEL_API_KEY", "")


# ─── Main Handler ──────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """Main Lambda entry point for Alexa Smart Home directives."""
    # Handle scheduled warmup events (keeps Lambda + backend warm)
    if event.get("source") == "aws.events" or event.get("detail-type") == "Scheduled Event":
        logger.info("Warmup ping — refreshing discovery cache")
        _call_backend("/api/alexa/lambda/refresh-cache", method="POST")
        return {"status": "warm"}

    logger.info("Directive: %s", json.dumps(event, indent=2))

    directive = event.get("directive", {})
    header = directive.get("header", {})
    namespace = header.get("namespace", "")
    name = header.get("name", "")

    try:
        if namespace == "Alexa.Authorization" and name == "AcceptGrant":
            return handle_accept_grant(directive)

        if namespace == "Alexa.Discovery" and name == "Discover":
            return handle_discovery(directive)

        if namespace == "Alexa" and name == "ReportState":
            return handle_report_state(directive)

        if namespace == "Alexa.PowerController":
            return handle_power_controller(directive)

        if namespace == "Alexa.ToggleController":
            return handle_toggle_controller(directive)

        if namespace == "Alexa.ModeController":
            return handle_mode_controller(directive)

        if namespace == "Alexa.RangeController":
            return handle_range_controller(directive)

        if namespace == "Alexa.SceneController":
            return handle_scene_controller(directive)

        logger.warning("Unhandled directive: %s.%s", namespace, name)
        return make_error_response(
            directive, "INVALID_DIRECTIVE",
            f"Unsupported directive: {namespace}.{name}"
        )

    except Exception as e:
        logger.error("Lambda error: %s", e, exc_info=True)
        return make_error_response(
            directive, "INTERNAL_ERROR",
            f"An internal error occurred: {e}"
        )


# ─── Backend Communication ─────────────────────────────────────────────────────

def _call_backend(path, method="GET", body=None, token=None):
    """Make a request to HomeSentinel backend."""
    if not HOMESENTINEL_URL:
        logger.warning("HOMESENTINEL_URL not configured")
        return None

    try:
        url = f"{HOMESENTINEL_URL}{path}"
        data = json.dumps(body).encode() if body else None
        headers = {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",  # Required for ngrok free tier
            "User-Agent": "HomeSentinel-Lambda/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if HOMESENTINEL_API_KEY:
            headers["X-API-Key"] = HOMESENTINEL_API_KEY
        req = request.Request(url, data=data, headers=headers, method=method)
        with request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        logger.error("Backend HTTP error: %s %s - %s", method, path, e)
        return None
    except Exception as e:
        logger.error("Backend call failed: %s %s - %s", method, path, e)
        return None


def _extract_token(directive):
    """Extract bearer token from any location in the directive."""
    # Endpoint scope (most directives)
    endpoint = directive.get("endpoint", {})
    scope = endpoint.get("scope", {})
    if scope.get("type") == "BearerToken":
        return scope.get("token")

    # Payload scope (Discovery)
    payload = directive.get("payload", {})
    scope = payload.get("scope", {})
    if scope.get("type") == "BearerToken":
        return scope.get("token")

    return None


def _store_token(token):
    """Forward bearer token to HomeSentinel backend for persistence."""
    if not token or not HOMESENTINEL_URL:
        return
    try:
        _call_backend("/api/alexa/lambda/token", "POST", {"access_token": token})
    except Exception as e:
        logger.error("Failed to store token: %s", e)


# ─── Utility Functions ─────────────────────────────────────────────────────────

def get_uuid():
    return str(uuid.uuid4())


def get_utc_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def make_response(directive, context_properties=None, payload=None):
    """Build a standard Alexa v3 Response."""
    header = directive.get("header", {})
    endpoint = directive.get("endpoint", {})

    response = {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "Response",
                "messageId": get_uuid(),
                "correlationToken": header.get("correlationToken", ""),
                "payloadVersion": "3",
            },
            "endpoint": {
                "endpointId": endpoint.get("endpointId", ""),
            },
            "payload": payload or {},
        },
    }

    if context_properties:
        response["context"] = {"properties": context_properties}

    return response


def make_state_report(directive, context_properties):
    """Build a StateReport response."""
    header = directive.get("header", {})
    endpoint = directive.get("endpoint", {})

    return {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "StateReport",
                "messageId": get_uuid(),
                "correlationToken": header.get("correlationToken", ""),
                "payloadVersion": "3",
            },
            "endpoint": {
                "endpointId": endpoint.get("endpointId", ""),
            },
            "payload": {},
        },
        "context": {
            "properties": context_properties,
        },
    }


def make_error_response(directive, error_type, message):
    """Build an ErrorResponse."""
    header = directive.get("header", {})
    endpoint = directive.get("endpoint", {})

    response = {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "ErrorResponse",
                "messageId": get_uuid(),
                "payloadVersion": "3",
            },
            "payload": {
                "type": error_type,
                "message": message,
            },
        },
    }

    correlation_token = header.get("correlationToken")
    if correlation_token:
        response["event"]["header"]["correlationToken"] = correlation_token

    endpoint_id = endpoint.get("endpointId")
    if endpoint_id:
        response["event"]["endpoint"] = {"endpointId": endpoint_id}

    return response


def _connectivity_property(is_online):
    """Build an EndpointHealth connectivity property."""
    return {
        "namespace": "Alexa.EndpointHealth",
        "name": "connectivity",
        "value": {"value": "OK" if is_online else "UNREACHABLE"},
        "timeOfSample": get_utc_timestamp(),
        "uncertaintyInMilliseconds": 6000,
    }


def _power_state_property(is_on):
    """Build a PowerController powerState property."""
    return {
        "namespace": "Alexa.PowerController",
        "name": "powerState",
        "value": "ON" if is_on else "OFF",
        "timeOfSample": get_utc_timestamp(),
        "uncertaintyInMilliseconds": 500,
    }


def _toggle_state_property(instance, is_on):
    """Build a ToggleController toggleState property."""
    return {
        "namespace": "Alexa.ToggleController",
        "instance": instance,
        "name": "toggleState",
        "value": "ON" if is_on else "OFF",
        "timeOfSample": get_utc_timestamp(),
        "uncertaintyInMilliseconds": 500,
    }


def _range_value_property(instance, value):
    """Build a RangeController rangeValue property."""
    return {
        "namespace": "Alexa.RangeController",
        "instance": instance,
        "name": "rangeValue",
        "value": value,
        "timeOfSample": get_utc_timestamp(),
        "uncertaintyInMilliseconds": 6000,
    }


def _mode_value_property(instance, value):
    """Build a ModeController mode property."""
    return {
        "namespace": "Alexa.ModeController",
        "instance": instance,
        "name": "mode",
        "value": value,
        "timeOfSample": get_utc_timestamp(),
        "uncertaintyInMilliseconds": 500,
    }


# ─── AcceptGrant Handler ──────────────────────────────────────────────────────

def handle_accept_grant(directive):
    """Handle Alexa.Authorization AcceptGrant during account linking."""
    payload = directive.get("payload", {})
    grant = payload.get("grant", {})
    grantee = payload.get("grantee", {})

    auth_code = grant.get("code", "")
    access_token = grantee.get("token", "")

    logger.info("AcceptGrant: code_len=%d", len(auth_code))

    if HOMESENTINEL_URL:
        _call_backend("/api/alexa/lambda/accept-grant", "POST", {
            "auth_code": auth_code,
            "access_token": access_token,
        })

    return {
        "event": {
            "header": {
                "namespace": "Alexa.Authorization",
                "name": "AcceptGrant.Response",
                "messageId": get_uuid(),
                "payloadVersion": "3",
            },
            "payload": {},
        }
    }


# ─── Discovery Handler ────────────────────────────────────────────────────────

def handle_discovery(directive):
    """Handle Alexa.Discovery Discover - return all HomeSentinel endpoints."""
    token = _extract_token(directive)
    if token:
        _store_token(token)

    # Fetch discovery data from backend
    data = _call_backend("/api/alexa/lambda/discover", token=token)
    endpoints = []

    if data and "endpoints" in data:
        endpoints = data["endpoints"]
    else:
        logger.warning("Backend unreachable for discovery, returning static endpoints")
        endpoints = _get_static_endpoints()

    logger.info("Discovery: returning %d endpoints", len(endpoints))

    return {
        "event": {
            "header": {
                "namespace": "Alexa.Discovery",
                "name": "Discover.Response",
                "messageId": get_uuid(),
                "payloadVersion": "3",
            },
            "payload": {
                "endpoints": endpoints,
            },
        }
    }


def _get_static_endpoints():
    """Return minimal static endpoints when backend is unreachable."""
    return [
        {
            "endpointId": "homesentinel-hub",
            "manufacturerName": "HomeSentinel",
            "friendlyName": "Home Network",
            "description": "HomeSentinel network monitoring hub",
            "displayCategories": ["NETWORK_HARDWARE"],
            "capabilities": [
                _capability_alexa(),
                _capability_endpoint_health(),
            ],
        },
    ]


# ─── Capability Builders ──────────────────────────────────────────────────────

def _capability_alexa():
    """Required Alexa interface capability for all endpoints."""
    return {
        "type": "AlexaInterface",
        "interface": "Alexa",
        "version": "3",
    }


def _capability_endpoint_health():
    """EndpointHealth capability - connectivity reporting."""
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.EndpointHealth",
        "version": "3.2",
        "properties": {
            "supported": [{"name": "connectivity"}],
            "proactivelyReported": False,
            "retrievable": True,
        },
    }


def _capability_power_controller():
    """PowerController - on/off for WiFi networks and devices."""
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.PowerController",
        "version": "3",
        "properties": {
            "supported": [{"name": "powerState"}],
            "proactivelyReported": False,
            "retrievable": True,
        },
    }


def _capability_toggle_controller(instance, friendly_name, semantics=None):
    """ToggleController - named toggle for specific features."""
    cap = {
        "type": "AlexaInterface",
        "interface": "Alexa.ToggleController",
        "version": "3",
        "instance": instance,
        "properties": {
            "supported": [{"name": "toggleState"}],
            "proactivelyReported": False,
            "retrievable": True,
        },
        "capabilityResources": {
            "friendlyNames": [
                {"@type": "text", "value": {"text": friendly_name, "locale": "en-US"}},
            ],
        },
    }
    if semantics:
        cap["semantics"] = semantics
    return cap


def _capability_range_controller(instance, friendly_name, min_val, max_val, unit=None):
    """RangeController - numeric range for signal strength, client count, etc."""
    cap = {
        "type": "AlexaInterface",
        "interface": "Alexa.RangeController",
        "version": "3",
        "instance": instance,
        "properties": {
            "supported": [{"name": "rangeValue"}],
            "proactivelyReported": False,
            "retrievable": True,
            "nonControllable": True,
        },
        "capabilityResources": {
            "friendlyNames": [
                {"@type": "text", "value": {"text": friendly_name, "locale": "en-US"}},
            ],
        },
        "configuration": {
            "supportedRange": {
                "minimumValue": min_val,
                "maximumValue": max_val,
                "precision": 1,
            },
        },
    }
    if unit:
        cap["configuration"]["unitOfMeasure"] = unit
    return cap


def _capability_mode_controller(instance, friendly_name, modes):
    """ModeController - enumerated modes for WiFi bands, security, etc."""
    supported_modes = []
    for mode_value, mode_name in modes.items():
        supported_modes.append({
            "value": mode_value,
            "modeResources": {
                "friendlyNames": [
                    {"@type": "text", "value": {"text": mode_name, "locale": "en-US"}},
                ],
            },
        })
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.ModeController",
        "version": "3",
        "instance": instance,
        "properties": {
            "supported": [{"name": "mode"}],
            "proactivelyReported": False,
            "retrievable": True,
            "nonControllable": True,
        },
        "capabilityResources": {
            "friendlyNames": [
                {"@type": "text", "value": {"text": friendly_name, "locale": "en-US"}},
            ],
        },
        "configuration": {
            "ordered": False,
            "supportedModes": supported_modes,
        },
    }


def _capability_scene_controller(supports_deactivation=False):
    """SceneController - for triggering actions like network reboot."""
    return {
        "type": "AlexaInterface",
        "interface": "Alexa.SceneController",
        "version": "3",
        "supportsDeactivation": supports_deactivation,
        "proactivelyReported": False,
    }


# ─── ReportState Handler ──────────────────────────────────────────────────────

def handle_report_state(directive):
    """Handle Alexa ReportState - return current device properties."""
    token = _extract_token(directive)
    endpoint = directive.get("endpoint", {})
    endpoint_id = endpoint.get("endpointId", "")

    logger.info("ReportState for: %s", endpoint_id)

    state = _call_backend(f"/api/alexa/lambda/state/{endpoint_id}", token=token)

    properties = []
    if state and "properties" in state:
        properties = state["properties"]
    else:
        # Fallback: at minimum report connectivity
        properties = [_connectivity_property(False)]

    return make_state_report(directive, properties)


# ─── PowerController Handler ──────────────────────────────────────────────────

def handle_power_controller(directive):
    """Handle Alexa.PowerController TurnOn/TurnOff.

    Used for:
    - Guest WiFi on/off
    - IoT network on/off
    - Deco node enable/disable
    """
    header = directive.get("header", {})
    endpoint = directive.get("endpoint", {})
    endpoint_id = endpoint.get("endpointId", "")
    name = header.get("name", "")
    token = _extract_token(directive)

    power_state = "ON" if name == "TurnOn" else "OFF"
    logger.info("PowerController %s for %s", power_state, endpoint_id)

    result = _call_backend("/api/alexa/lambda/command", "POST", {
        "endpoint_id": endpoint_id,
        "namespace": "Alexa.PowerController",
        "name": name,
        "command": "power",
        "value": power_state,
    }, token=token)

    if result and result.get("error"):
        return make_error_response(
            directive, "ENDPOINT_UNREACHABLE", result["error"]
        )

    properties = [
        _power_state_property(power_state == "ON"),
        _connectivity_property(True),
    ]

    return make_response(directive, properties)


# ─── ToggleController Handler ─────────────────────────────────────────────────

def handle_toggle_controller(directive):
    """Handle Alexa.ToggleController TurnOn/TurnOff.

    Used for named toggles:
    - GuestWiFi.toggle - guest network
    - IoTNetwork.toggle - IoT network
    - WiFi24.toggle - 2.4GHz band
    - WiFi5.toggle - 5GHz band
    - WiFi6.toggle - 6GHz band
    """
    header = directive.get("header", {})
    endpoint = directive.get("endpoint", {})
    endpoint_id = endpoint.get("endpointId", "")
    name = header.get("name", "")
    instance = header.get("instance", "")
    token = _extract_token(directive)

    toggle_state = name == "TurnOn"
    logger.info("ToggleController %s instance=%s for %s", name, instance, endpoint_id)

    result = _call_backend("/api/alexa/lambda/command", "POST", {
        "endpoint_id": endpoint_id,
        "namespace": "Alexa.ToggleController",
        "instance": instance,
        "name": name,
        "command": "toggle",
        "value": "ON" if toggle_state else "OFF",
    }, token=token)

    if result and result.get("error"):
        return make_error_response(
            directive, "ENDPOINT_UNREACHABLE", result["error"]
        )

    properties = [
        _toggle_state_property(instance, toggle_state),
        _connectivity_property(True),
    ]

    return make_response(directive, properties)


# ─── ModeController Handler ───────────────────────────────────────────────────

def handle_mode_controller(directive):
    """Handle Alexa.ModeController SetMode.

    Used for read-only mode reporting (WiFi security mode, connection type).
    """
    header = directive.get("header", {})
    endpoint = directive.get("endpoint", {})
    endpoint_id = endpoint.get("endpointId", "")
    instance = header.get("instance", "")
    payload = directive.get("payload", {})
    mode = payload.get("mode", "")
    token = _extract_token(directive)

    logger.info("ModeController SetMode instance=%s mode=%s for %s", instance, mode, endpoint_id)

    result = _call_backend("/api/alexa/lambda/command", "POST", {
        "endpoint_id": endpoint_id,
        "namespace": "Alexa.ModeController",
        "instance": instance,
        "command": "mode",
        "value": mode,
    }, token=token)

    if result and result.get("error"):
        return make_error_response(
            directive, "NOT_SUPPORTED_IN_CURRENT_MODE",
            result.get("error", "Mode change not supported")
        )

    properties = [
        _mode_value_property(instance, mode),
        _connectivity_property(True),
    ]

    return make_response(directive, properties)


# ─── RangeController Handler ──────────────────────────────────────────────────

def handle_range_controller(directive):
    """Handle Alexa.RangeController SetRangeValue/AdjustRangeValue.

    Range controllers are non-controllable (read-only sensors) for:
    - Signal strength, client count, CPU usage, memory usage
    """
    header = directive.get("header", {})
    instance = header.get("instance", "")

    logger.info("RangeController: instance=%s (read-only, rejecting write)", instance)

    return make_error_response(
        directive, "NOT_SUPPORTED_IN_CURRENT_MODE",
        f"The {instance} sensor is read-only and cannot be adjusted"
    )


# ─── SceneController Handler ──────────────────────────────────────────────────

def handle_scene_controller(directive):
    """Handle Alexa.SceneController Activate/Deactivate.

    Used for:
    - Network reboot scene
    - Speed test scene
    """
    header = directive.get("header", {})
    endpoint = directive.get("endpoint", {})
    endpoint_id = endpoint.get("endpointId", "")
    name = header.get("name", "")
    token = _extract_token(directive)

    logger.info("SceneController %s for %s", name, endpoint_id)

    result = _call_backend("/api/alexa/lambda/command", "POST", {
        "endpoint_id": endpoint_id,
        "namespace": "Alexa.SceneController",
        "name": name,
        "command": "scene",
        "value": name,
    }, token=token)

    cause_type = "VOICE_INTERACTION"

    response = {
        "event": {
            "header": {
                "namespace": "Alexa.SceneController",
                "name": "ActivationStarted" if name == "Activate" else "DeactivationStarted",
                "messageId": get_uuid(),
                "payloadVersion": "3",
            },
            "endpoint": {
                "endpointId": endpoint_id,
            },
            "payload": {
                "cause": {"type": cause_type},
                "timestamp": get_utc_timestamp(),
            },
        },
    }

    correlation_token = header.get("correlationToken")
    if correlation_token:
        response["event"]["header"]["correlationToken"] = correlation_token

    return response