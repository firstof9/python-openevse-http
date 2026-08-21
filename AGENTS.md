# Agent Guidelines for python-openevse-http

This document outlines key architecture, conventions, workflows, and testing practices for agentic assistants operating in this repository.

---

## 1. Project Overview & Architecture

`python-openevse-http` is an asynchronous Python library for interacting with OpenEVSE electric vehicle chargers via their HTTP REST API, WebSocket streams, and RAPI commands.

### Core Modules & Mixins
The main client class `OpenEVSE` in `openevsehttp/client.py` inherits from multiple mixins:
- **`openevsehttp/client.py`**: Core client lifecycle, authentication, request processing (`process_request`, `send_command`), status updates (`update`), and session management.
- **`openevsehttp/commands.py` (`CommandsMixin`)**: Charger commands (e.g. `set_override`, `toggle_override`, `clear_override`, `set_current`, `set_charge_mode`, `divert_mode`, `set_shaper`, `toggle_shaper`, `restart_wifi`, `restart_evse`, `update_firmware`).
- **`openevsehttp/properties.py` (`PropertiesMixin`)**: Charger properties, configuration parsing, state decoding (`states`, `divert_mode`), firmware version parsing.
- **`openevsehttp/sensors.py` (`SensorsMixin`)**: Sensor values, telemetry, power/voltage calculations.
- **`openevsehttp/websocket.py` (`WebsocketMixin`, `OpenEVSEWebsocket`)**: Real-time websocket communication and state change listeners.
- **`openevsehttp/exceptions.py`**: Typed library exceptions inheriting from `OpenEVSEError`.

### Client Session Requirement
- `OpenEVSE` uses caller-provided `aiohttp.ClientSession` (via `session=...`). If not provided, accessing network operations raises `RuntimeError(ERROR_SESSION_REQUIRED)`.
- The session must run on the active event loop.

---

## 2. Firmware Version Handling & Upstream Validation

OpenEVSE chargers run various firmware versions (v2.x, v3.x, v4.x, v5.x) with different capabilities:
- **`self._version_check(min_version, max_version="")`**: Use this helper to conditionally execute HTTP API endpoints (v4+) versus RAPI command fallbacks (v2/v3, e.g. `$FE`, `$FS`, `$SC`, `$FR`).
- Always handle version edge cases (e.g. non-semver development strings like `4.1.2.dev`).
- Raise `UnsupportedFeature` if a feature is not supported on older firmware.

### Validating Endpoints Against Firmware Sources
When adding or updating endpoints, payload keys, or RAPI commands, cross-reference against:
- **WiFi Gateway (v3/v4/v5)**: [`OpenEVSE/ESP32_WiFi_V4.x`](https://github.com/OpenEVSE/ESP32_WiFi_V4.x) (routes in `src/http.cpp`, `src/web_server.cpp`)
- **Legacy WiFi (v2)**: [`OpenEVSE/ESP8266_WiFi_v2.x`](https://github.com/OpenEVSE/ESP8266_WiFi_v2.x)
- **Controller / RAPI**: [`OpenEVSE/open_evse`](https://github.com/OpenEVSE/open_evse) (commands in `src/rapi.cpp`)
Verify HTTP methods, expected JSON fields, success/error payload shapes, and version thresholds.

---

## 3. Exception Handling

All custom exceptions inherit from `OpenEVSEError(Exception)`:
- `CommandFailedError`: Command execution failure, RAPI rejection (`$NK`), or error HTTP response.
- `UnknownStateError`: Required state or configuration missing before command execution (e.g. toggle state).
- `FirmwareResolutionError`: GitHub release asset resolution failure.
- `AuthenticationError`: HTTP 401 / auth failures.
- `UnsupportedFeature`: Feature not available for current firmware version.
- `ParseJSONError`, `InvalidType`, `MissingMethod`, `MissingSerial`, `AlreadyListening`.

Export all public exception classes in `openevsehttp/__init__.py`.

---

## 4. Development & Testing Workflow

### Running Tests
Use `tox` for isolated environments:
```bash
# Run unit tests on Python 3.14 / active environment
tox -e py314

# Or run pytest directly within the tox environment
.tox/py314/bin/pytest

# Target specific test files
.tox/py314/bin/pytest tests/test_commands.py -k "test_toggle_override"
```

### Linting & Formatting
```bash
# Run ruff formatting check & linter
tox -e lint

# Format code automatically
.tox/lint/bin/ruff format ./

# Run linter with auto-fixes
.tox/lint/bin/ruff check --fix openevsehttp tests
```

### Type Checking
```bash
tox -e mypy
# Or directly:
.tox/mypy/bin/mypy openevsehttp
```

---

## 5. Testing & Mocking Guidelines

- Tests use `pytest` with `pytest-asyncio` (`asyncio_default_fixture_loop_scope = "function"`).
- Test fixtures in `tests/conftest.py`:
  - `test_charger`: Standard v4 charger client with mocked endpoints.
  - `test_charger_v2`: Legacy v2 firmware mock.
  - `test_charger_new`: Newer v4 fixture with shaper and modern endpoints.
  - `test_charger_auth`: Authenticated charger mock.
  - `mock_aioclient`: `AiohttpClientMocker` instance for intercepting HTTP requests (`get`, `post`, `patch`, `delete`).
- Fixture data files are located in `tests/fixtures/` (`v4_json/`, `v2_json/`).

---

## 6. Commit & Pull Request Guidelines

- **Semantic PR Titles**: Use conventional commit titles matching `.github/release-drafter.yml`:
  - `feat:` New features / enhancements
  - `fix:` Bug fixes
  - `refactor:` Refactoring / code quality
  - `test:` Test additions / updates
  - `docs:` Documentation changes
  - `chore:` Maintenance / dependency updates
- Fill out the checklist in `.github/pull_request_template.md`.
- Ensure all tests (`tox -e py314`), linting (`tox -e lint`), and type checks (`tox -e mypy`) pass before submitting PRs.
