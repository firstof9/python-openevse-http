---
name: openevse-api-guide
description: >-
  Use this skill when implementing, refactoring, or testing OpenEVSE charger
  commands, REST API endpoints, RAPI commands, properties, or exception handling in python-openevse-http.
---

# OpenEVSE API & Command Implementation Guide

This skill provides architectural guidelines, endpoint conventions, and error handling patterns for developing `python-openevse-http`.

## Architecture

The main client `OpenEVSE` combines several mixins:
- `CommandsMixin` (`openevsehttp/commands.py`): Command execution methods.
- `PropertiesMixin` (`openevsehttp/properties.py`): Configuration & state properties.
- `SensorsMixin` (`openevsehttp/sensors.py`): Energy, current, voltage, temperature telemetry.
- `WebsocketMixin` (`openevsehttp/websocket.py`): Real-time event streams.

## Endpoints & RAPI Commands Reference

| Action | HTTP Endpoint (v4+) | RAPI Command (v2/v3) | Method |
| :--- | :--- | :--- | :--- |
| Status | `/status` | N/A | GET |
| Config | `/config` | N/A | GET / POST |
| Manual Override | `/override` | `$FE` (enable) / `$FS` (sleep) | GET / POST / PATCH / DELETE |
| Soft Current Limit | `/override` (charge_current) | `$SC <amps> [N\|V]` | POST |
| Shaper Mode | `/shaper` | N/A | POST |
| Divert Mode | `/divertmode` or `/config` | N/A | POST |
| Module Restart | `/restart` (`device: gateway\|evse`) | `$FR` (evse restart) | POST |
| Firmware Update | `/update` | N/A | POST (multipart or JSON URL) |

## Firmware Version Branching

Always check firmware compatibility using `self._version_check(min_version)`:
```python
if self._version_check("4.0.1"):
    # Use HTTP REST endpoint
    response = await self.process_request(url=f"{self.url}override", method="patch")
else:
    # Fallback to RAPI command for older firmware
    response, msg = await self.send_command("$FE" if state == 254 else "$FS")
```

If a feature is not supported on older firmware:
```python
if not self._version_check("4.1.0"):
    _LOGGER.debug("Feature not supported for older firmware.")
    raise UnsupportedFeature
```

## Exception Handling Conventions

All custom exceptions inherit from `OpenEVSEError(Exception)`.

- **`CommandFailedError`**: Raise when a command returns an error response, fails HTTP verification, or returns `$NK` / `RAPI_ERRORS`.
- **`UnknownStateError`**: Raise when prior charger state or configuration is required to determine the command payload (e.g. toggling) but is missing or `None`.
- **`FirmwareResolutionError`**: Raise when GitHub release download URL cannot be determined from the release metadata.
- **`UnsupportedFeature`**: Raise when charger firmware is below the minimum supported version for a feature.
- **`AuthenticationError`**: Raise on 401 unauthorized.

```python
from .exceptions import CommandFailedError, UnknownStateError, UnsupportedFeature
```

## Validating Endpoints Against Firmware Repositories

When adding, modifying, or debugging endpoints and RAPI commands, cross-reference against the upstream OpenEVSE firmware sources:

- **WiFi Gateway Firmware (v3/v4/v5)**: [`OpenEVSE/ESP32_WiFi_V4.x`](https://github.com/OpenEVSE/ESP32_WiFi_V4.x)
- **Legacy WiFi Firmware (v2)**: [`OpenEVSE/ESP8266_WiFi_v2.x`](https://github.com/OpenEVSE/ESP8266_WiFi_v2.x)
- **OpenEVSE Controller Firmware (RAPI)**: [`OpenEVSE/open_evse`](https://github.com/OpenEVSE/open_evse)

### What to Verify in Firmware Sources:
1. **Route & Method Handlers**:
   - Check `src/http.cpp`, `src/web_server.cpp`, or `src/web_server.h` in `ESP32_WiFi_V4.x` to confirm HTTP methods (`GET`, `POST`, `PATCH`, `DELETE`).
   - Confirm expected query parameters or JSON body fields (e.g. `divertmode=...`, `{"device": "gateway"}`, `{"charge_current": ...}`).
2. **Response Formats & Statuses**:
   - Verify success and error response payloads (e.g., `{"msg": "done"}`, `{"result": "OK", "msg": "..."}`, or plain string messages like `"Current Shaper state changed"`).
   - Update `SUCCESS_ANSWERS` in `openevsehttp/const.py` if new success indicators are introduced.
3. **Firmware Version Thresholds**:
   - Check git history or release tags in `ESP32_WiFi_V4.x` to determine when a route or feature was introduced, ensuring accurate `_version_check("x.y.z")` values.
4. **RAPI Command Specifications**:
   - Check `src/rapi.cpp` or OpenEVSE controller docs for valid RAPI commands (e.g., `$SC`, `$FE`, `$FS`, `$FR`, `$ST`) and return formats (`$OK`, `$NK`).
5. **Mock Test Fixtures**:
   - Update or add mock JSON payloads under `tests/fixtures/v4_json/` and `tests/fixtures/v2_json/` to mirror real firmware response shapes.

## Writing Tests for Commands

When testing command methods:
1. Use fixtures from `tests/conftest.py` (`test_charger`, `test_charger_v2`, `test_charger_new`).
2. Mock responses using `mock_aioclient`:
   ```python
   mock_aioclient.post(
       TEST_URL_CONFIG,
       status=200,
       body='{"msg": "done"}',
   )
   ```
3. Test success paths, failure responses (`CommandFailedError`), missing state paths (`UnknownStateError`), and older firmware version behavior (`UnsupportedFeature` / RAPI commands).
