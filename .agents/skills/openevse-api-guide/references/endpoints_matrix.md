# OpenEVSE HTTP API & Firmware Endpoint Matrix

This reference document compiles all known HTTP REST API endpoints, WebSocket paths, and RAPI fallback commands across OpenEVSE WiFi firmware generations:
- **v4.x / v5.x (Active Development)**: [`OpenEVSE/openevse_esp32_firmware`](https://github.com/OpenEVSE/openevse_esp32_firmware) (formerly `ESP32_WiFi_V4.x`).
- **v3.x (Legacy ESP32 - EOL)**: [`OpenEVSE/ESP32_WiFi_V3.x`](https://github.com/OpenEVSE/ESP32_WiFi_V3.x) (e.g. v3.3.1).
- **v2.x (Legacy ESP8266 - EOL)**: [`OpenEVSE/ESP8266_WiFi_v2.x`](https://github.com/OpenEVSE/ESP8266_WiFi_v2.x) (up to v2.9.1).
- **Controller Firmware**: [`OpenEVSE/open_evse`](https://github.com/OpenEVSE/open_evse) (RAPI backend).

> [!IMPORTANT]
> **Active Development Warning**: Development on **v2.x** and **v3.x** has ended. Active development occurs exclusively on **v4.x / v5.x** in `OpenEVSE/openevse_esp32_firmware`. Whenever validating new features, routes, or bugfixes, always inspect `OpenEVSE/openevse_esp32_firmware` as the primary source of truth.

---

## 1. Endpoint Availability Matrix

| Route | Supported Methods | v2.x (ESP8266) | v3.x (ESP32) | v4.x / v5.x (ESP32) | RAPI Fallback (v2/v3) | python-openevse-http Status |
| :--- | :--- | :---: | :---: | :---: | :--- | :---: |
| `/status` | `GET`, `POST` | `GET` only | `GET` only | `GET`, `POST` | N/A | ✅ Fully Supported |
| `/config` | `GET`, `POST` | `GET`, `POST` | `GET`, `POST` | `GET`, `POST` | N/A | ✅ Fully Supported |
| `/override` | `GET`, `POST`, `PATCH`, `DELETE` | ❌ | ❌ | ✅ (v4.0.0+) | `$FE` (enable) / `$FS` (sleep), `$SC` | ✅ Fully Supported |
| `/claims` | `GET`, `POST`, `DELETE` | ❌ | ❌ | ✅ (v4.0.0+) | N/A | ✅ Fully Supported |
| `/limit` | `GET`, `POST`, `DELETE` | ❌ | ❌ | ✅ (v4.0.0+) | `$SH` (kWh limit), `$S3` (time limit) | ✅ Fully Supported |
| `/shaper` | `POST` | ❌ | ❌ | ✅ (v4.0.0+) | N/A | ✅ Fully Supported |
| `/divertmode` | `POST` | ✅ (`/divertmode`) | ✅ (`/divertmode`) | ✅ (`/divertmode`) | N/A (updates config flags) | ✅ Fully Supported |
| `/restart` | `POST` | ✅ (`/restart`) | ✅ (`/restart`) | ✅ (`/restart`) | `$FR` (EVSE controller reboot) | ✅ Fully Supported |
| `/r` or `/rapi` | `GET`, `POST` | `GET` (html/json) | `GET`, `POST` | `POST` (Mongoose) | Direct RAPI | ✅ Fully Supported |
| `/ws` | `WebSocket` | ✅ | ✅ | ✅ | N/A | ✅ Fully Supported |
| `/schedule` | `GET`, `POST`, `DELETE` | ❌ | ❌ | ✅ (v4.0.0+) | `$ST` / `$GD` | ⚠️ Retrieval Supported |
| `/schedule/plan` | `GET` | ❌ | ❌ | ✅ (v4.1.0+) | N/A | ❌ Not Implemented |
| `/time` | `GET`, `POST` | ❌ | ❌ (`/settime`) | ✅ (v4.0.0+) | `$S1` (RTC set) | ✅ Fully Supported |
| `/settime` | `GET`, `POST` | ❌ | ✅ | ⚠️ Legacy alias | `$S1` | ✅ Fully Supported |
| `/emeter` | `DELETE` | ❌ | ❌ | ✅ (v4.0.0+) | N/A | ❌ Not Implemented |
| `/notifications` | `GET` | ❌ | ❌ | ✅ (v5.1.0+) | N/A | ❌ Not Implemented |
| `/notifications/ack` | `POST` | ❌ | ❌ | ✅ (v5.1.0+) | N/A | ❌ Not Implemented |
| `/update` | `GET`, `POST` | `GET`, `POST` | `GET`, `POST` | `GET`, `POST` | N/A | ✅ Fully Supported |
| `/logs` | `GET` | ❌ | ❌ | ✅ (v4.0.0+) | N/A | ❌ Not Implemented |
| `/logs/export` | `GET` | ❌ | ❌ | ✅ (v4.0.0+) | N/A | ❌ Not Implemented |
| `/certificates` | `GET`, `POST`, `DELETE` | ❌ | ❌ | ✅ (v4.0.0+) | N/A | ❌ Not Implemented |
| `/scan` | `GET` | ✅ | ✅ | ✅ | N/A | ❌ Not Implemented |
| `/apoff` | `GET`, `POST` | ✅ | ✅ | ✅ | N/A | ❌ Not Implemented |
| `/reset` | `GET`, `POST` | ✅ | ✅ | ✅ | N/A | ❌ Not Implemented |
| `/rfid/add` | `POST` | ❌ | ❌ | ✅ (v4.0.0+) | N/A | ❌ Not Implemented |
| `/rfid/users` | `GET`, `POST`, `DELETE` | ❌ | ❌ | ✅ (v5.0.0+) | N/A | ❌ Not Implemented |
| `/relay/reset` | `POST` | ❌ | ❌ | ✅ (v5.1.0+) | `$FH` | ✅ Fully Supported |
| `/relay/recovery` | `POST` | ❌ | ❌ | ✅ (v5.1.0+) | `$FK` | ✅ Fully Supported |
| `/cabletemp` | `GET`, `POST` | ❌ | ❌ | ✅ (v5.1.0+) | `$GN`, `$SN` | ✅ Fully Supported |
| `/teslaveh` / `/tesla/vehicles` | `GET` | ❌ | ✅ (`/teslaveh`) | ✅ | N/A | ❌ Not Implemented |
| `/energy/raw`, `/daily`, etc. | `GET` | ❌ | ❌ | ✅ (v4.0.0+) | N/A | ❌ Not Implemented |
| `/migrate/expand16mb` | `POST` | ❌ | ❌ | ✅ (v5.1.0+) | N/A | ❌ Not Implemented |

---

## 2. Core Endpoint Payload Differences

### A. `/config` (Device Configuration & Identification)

| Field Key | Type | v2.x (ESP8266) | v3.x (ESP32) | v4.x / v5.x (ESP32) | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `wifi_serial` | `string` | ❌ (None) | ❌ (None) | ✅ | Formatted uppercase hardware MAC (e.g. `1234567890AB`). **Missing on v2/v3!** |
| `hostname` | `string` | ✅ (`"openevse"`) | ✅ (`"openevse-XXXX"`) | ✅ (`"openevse-XXXX"`) | Configured hostname. |
| `mqtt_announce_topic` | `string` | ✅ | ✅ | ✅ | Defaults to `"openevse/announce/XXXX"`. |
| `version` | `string` | ✅ (`"2.9.1"`) | ✅ (`"3.3.1"`) | ✅ (`"4.1.2"`) | WiFi gateway firmware version string. |
| `firmware` | `string` | ✅ (`"5.0.1"`) | ✅ | ✅ (`"7.1.3"`) | EVSE controller firmware version string. |
| `protocol` | `string` | ✅ (`"4.0.1"`) | ✅ (`"-"`) | ✅ (`"-"`) | RAPI protocol version. |
| `buildenv` | `string` | ❌ | ❌ | ✅ (e.g. `"openevse_wifi_v1"`) | PlatformIO build target name. |
| `d9_support` | `bool` | ❌ | ❌ | ✅ (v5.x) | Signals OpenEVSE D9+ controller hardware support. |
| `rfid_enabled` | `bool` | ❌ | ❌ | ✅ (v4.1.0+) | Virtual flag mask. |
| `led_brightness` | `int` | ❌ | ❌ | ✅ (v4.1.0+) | RGB LED brightness (0-255). |
| `flags` | `int` | ✅ (24-bit) | ✅ (24-bit) | ✅ (32-bit) | Bitmask of enabled services and configurations. |

### B. `/status` (Telemetry & State Monitoring)

| Field Key | Type | v2.x (ESP8266) | v3.x (ESP32) | v4.x / v5.x (ESP32) | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `state` | `int` | ✅ | ✅ | ✅ | EVSE state: 1=Ready, 2=Connected, 3=Charging, 254=Sleeping, 255=Disabled. |
| `amp` | `float` | ✅ | ✅ | ✅ | Charging current in Amperes. |
| `voltage` | `int\|float` | ✅ | ✅ | ✅ | Voltage in Volts (e.g. 240). |
| `pilot` | `int` | ✅ | ✅ | ✅ | Pilot limit in Amperes. |
| `macaddress` | `string` | ❌ | ❌ | ✅ (v4.x+) | Hardware MAC address (e.g. `"AA:BB:CC:DD:EE:FF"`). |
| `ipaddress` | `string` | ✅ | ✅ | ✅ | Local IP address. |
| `shaper` | `int` | ❌ | ❌ | ✅ (v4.0.0+) | Current Shaper active: 0=Disabled, 1=Enabled. |
| `shaper_live_pwr` | `int` | ❌ | ❌ | ✅ (v4.0.0+) | Shaper live grid power (W). |
| `shaper_cur` | `float` | ❌ | ❌ | ✅ (v4.0.0+) | Shaper dynamically calculated max current (A). |
| `vehicle_soc` | `int` | ❌ | ❌ | ✅ (v4.1.0+) | Vehicle battery SoC (%). Pushed via `POST /status`. |
| `vehicle_range` | `int` | ❌ | ❌ | ✅ (v4.1.0+) | Vehicle range (km or miles). |
| `time_to_full_charge` | `int` | ❌ | ❌ | ✅ (v4.1.0+) | Seconds until complete charge. |
| `notifications` | `object` | ❌ | ❌ | ✅ (v5.1.0+) | Summary notifications object `{"count": N, "severity": "..."}`. |

---

## 3. Actuator Security & CSRF (`actuatorMethodAllowed`)

In **v4.x / v5.x** firmware, destructive actuators (`/reset`, `/restart`, `/apoff`, `/divertmode`, `/shaper`, `/settime`, `/rfid/add`, `/relay/reset`, `/relay/recovery`) include CSRF protection:
- Calls must be sent via **`POST`** (or non-GET HTTP methods).
- If sent via `GET`, the firmware rejects with `403 Forbidden` unless the header `X-Requested-With: OpenEVSE` is present.
- `python-openevse-http` always sends actuators via `POST` or `PATCH`.

---

## 4. Upstream Repository Reference Links

When cross-checking implementation or adding support for new firmware features:
- **Active WiFi Gateway Codebase**: [`OpenEVSE/openevse_esp32_firmware`](https://github.com/OpenEVSE/openevse_esp32_firmware)
  - HTTP routes & endpoints: `src/web_server.cpp`
  - `/config` serialization: `src/web_server_config.cpp` & `src/app_config.cpp`
  - Shaper & Claims: `src/current_shaper.cpp`, `src/web_server_claims.cpp`
  - Override handler: `src/web_server.cpp` (`handleOverride`)
- **Legacy ESP32 Firmware (EOL)**: [`OpenEVSE/ESP32_WiFi_V3.x`](https://github.com/OpenEVSE/ESP32_WiFi_V3.x)
- **Legacy ESP8266 Firmware (EOL)**: [`OpenEVSE/ESP8266_WiFi_v2.x`](https://github.com/OpenEVSE/ESP8266_WiFi_v2.x)
- **Controller RAPI Source**: [`OpenEVSE/open_evse`](https://github.com/OpenEVSE/open_evse) (specifically `src/rapi.cpp`)
