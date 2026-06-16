![Codecov branch](https://img.shields.io/codecov/c/github/firstof9/python-openevse-http/main?style=flat-square)
![GitHub commit activity (branch)](https://img.shields.io/github/commit-activity/m/firstof9/python-openevse-http?style=flat-square)
![GitHub last commit](https://img.shields.io/github/last-commit/firstof9/python-openevse-http?style=flat-square)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/firstof9/python-openevse-http?style=flat-square)

# python-openevse-http

A Python library for communicating with [OpenEVSE](https://www.openevse.com/) chargers via the HTTP API on ESP8266 and ESP32-based WiFi modules.

## Features

- **Asynchronous**: Built on `aiohttp` for non-blocking I/O.
- **WebSocket Support**: Real-time updates for charger status.
- **Firmware Support**: Compatible with ESP8266 (2.x) and ESP32 (4.x+) WiFi firmware.
- **Comprehensive API**:
    - Query status and configuration.
    - Manage manual overrides.
    - Control charging claims and limits.
    - Handle schedules.
    - **Shaper Toggle**: Enable or disable the grid shaper feature (requires firmware 4.0.0+).

## Installation

```bash
pip install python_openevse_http
```

## Quick Start

```python
import asyncio
import aiohttp
from openevsehttp import OpenEVSE

async def main():
    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE("192.168.1.30", session=session)
        await charger.update()

        print(f"Charger State: {charger.status}")
        print(f"Current Charge: {charger.charge_current}A")

        if charger.shaper_active:
            print("Shaper is active, disabling...")
        else:
            print("Shaper is inactive, enabling...")

        await charger.toggle_shaper()
        await charger.ws_disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```
### HTTPS and SSL Verification Options

If your OpenEVSE WiFi/ethernet module uses HTTPS (e.g. with a self-signed certificate), you can initialize the client with `ssl=True` and configure SSL verification:

```python
        # Connect using HTTPS, and disable certificate verification
        charger = OpenEVSE(
            "192.168.1.30",
            session=session,
            ssl=True,
            ssl_verify=False,
        )
```

## API Support Matrix

| Endpoint | Methods | Supported | Description |
| :--- | :--- | :---: | :--- |
| `/status` | GET, POST | ✅ | Real-time status, sensors, and **Vehicle SoC** pushing |
| `/config` | GET, POST | ✅ | System and WiFi configuration |
| `/override` | GET, POST, PATCH, DELETE | ✅ | Manual charging overrides & current limits |
| `/claims` | GET, POST, DELETE | ✅ | Client-based charging claims |
| `/schedule` | GET, POST | ⚠️ | Charging schedule management (Retrieval only) |
| `/limit` | GET, POST, DELETE | ✅ | Charge limits (Time, Energy, SoC) |
| `/shaper` | POST | ✅ | Grid shaper control (v4.0.0+) |
| `/restart` | POST | ✅ | Reboot WiFi gateway or EVSE module |
| `/divertmode` | POST | ✅ | Solar divert mode control |
| `/r` (RAPI) | POST | ✅ | Direct RAPI command interface |
| `/ws` | GET | ✅ | WebSocket real-time updates |
| `/time` | GET, POST | ❌ | RTC and NTP time settings |
| `/logs` | GET | ❌ | System and debug event logs |
| `/emeter` | DELETE | ❌ | Energy meter reset |
| `/wifi` | GET, POST | ❌ | Network scanning and AP configuration |
| `/tesla` | GET | ❌ | Tesla vehicle integration |
| `/certificates`| GET, POST, DELETE | ❌ | SSL/TLS certificate management |
| `/schedule/plan`| GET | ❌ | Schedule planning and optimization |
| `/update` | POST | ✅ | Firmware update interface |
| `/rfid/add` | POST | ❌ | RFID tag management |

✅ = Fully Supported \| ⚠️ = Partial Support \| ❌ = Not yet implemented

## License

This project is licensed under the Apache-2.0 License.
