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
    - **Time Synchronization & RTC**: Manage time, timezone, and NTP sync (requires firmware 4.0.0+).
    - **Event Logs**: Retrieve diagnostic log blocks and log event history (requires firmware 4.0.0+).
    - **Certificates**: Manage SSL/TLS Root CA and client certificates (requires firmware 4.0.0+).
    - **RFID Management**: RFID tag pairing mode and tag-to-user mappings (requires firmware 4.0.0+ / 5.0.0+).
    - **Relay Diagnostics**: Stuck relay recovery cycle and contact-life estimation reset (requires firmware 5.1.0+).
    - **Cable Temperature Monitoring**: Cable temperature sensor configuration and monitoring (requires firmware 5.1.0+).
    - **Energy Meter Reset**: Reset the energy meter counters with soft/hard options (requires firmware 4.0.0+).
    - **Advisory Notifications**: Retrieve gateway advisory notifications and acknowledge/mute active advisories (requires firmware 5.1.0+).

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

If your OpenEVSE WiFi/ethernet module uses HTTPS, you can configure the client to connect securely using the `ssl=True` parameter:

```python
        # Connect securely using HTTPS (validating SSL/TLS certificates)
        charger = OpenEVSE(
            "192.168.1.30",
            session=session,
            ssl=True,
        )
```

#### Bypassing SSL Verification (Self-Signed Certificates)

> [!WARNING]
> Disabling SSL certificate validation (`ssl_verify=False`) disables TLS verification and exposes the connection to Man-in-the-Middle (MITM) attacks. Only use this configuration when connecting to an OpenEVSE module with a self-signed certificate over a trusted local network.

To bypass certificate verification:

```python
        # Connect using HTTPS, and disable certificate verification
        charger = OpenEVSE(
            "192.168.1.30",
            session=session,
            ssl=True,
            ssl_verify=False,
        )
```

### GitHub API Token (Optional)

When performing firmware update checks (`charger.firmware_check()`) or automatic firmware updates (`charger.update_firmware()`), the library queries GitHub's Releases API. To avoid hitting unauthenticated rate limits (60 requests/hour), you can supply a GitHub personal access token (PAT):

```python
        # Provide a GitHub token during client initialization
        charger = OpenEVSE(
            "192.168.1.30",
            session=session,
            github_token="ghp_your_github_token_here",
        )

        # Or set / update dynamically via property
        charger.github_token = "ghp_your_github_token_here"

        # Or pass per-call
        latest = await charger.firmware_check(github_token="ghp_your_github_token_here")
```

## API Support Matrix

| Endpoint | Methods | Supported | Description |
| :--- | :--- | :---: | :--- |
| `/status` | GET, POST | ✅ | Real-time status, sensors, and **Vehicle SoC** pushing |
| `/config` | GET, POST | ✅ | System and WiFi configuration |
| `/override` | GET, POST, PATCH, DELETE | ✅ | Manual charging overrides & current limits |
| `/claims` | GET, POST, DELETE | ✅ | Client-based charging claims |
| `/schedule` | GET, POST, DELETE | ✅ | Charging schedule management (v4.0.0+) |
| `/limit` | GET, POST, DELETE | ✅ | Charge limits (Time, Energy, SoC) |
| `/shaper` | POST | ✅ | Grid shaper control (v4.0.0+) |
| `/restart` | POST | ✅ | Reboot WiFi gateway or EVSE module |
| `/divertmode` | POST | ✅ | Solar divert mode control |
| `/r` (RAPI) | POST | ✅ | Direct RAPI command interface |
| `/ws` | GET | ✅ | WebSocket real-time updates |
| `/time` | GET, POST | ✅ | RTC and NTP time settings (v4.0.0+) |
| `/settime` | POST | ✅ | Legacy time setting interface (v3.x / fallback to `$S1` on v2.x) |
| `/logs` | GET | ✅ | Event log block bounds and block events (v4.0.0+) |
| `/emeter` | DELETE | ✅ | Energy meter reset (v4.0.0+) |
| `/notifications` | GET | ✅ | Gateway advisory notifications list (v5.1.0+) |
| `/notifications/ack` | POST | ✅ | Acknowledge/mute active advisory notification (v5.1.0+) |
| `/wifi` | GET, POST | ❌ | Network scanning and AP configuration |
| `/tesla` | GET | ❌ | Tesla vehicle integration |
| `/certificates`| GET, POST, DELETE | ✅ | SSL/TLS certificate management (v4.0.0+) |
| `/schedule/plan`| GET | ✅ | Schedule planning and optimization (v4.1.0+) |
| `/update` | POST | ✅ | Firmware update interface |
| `/relay/recovery` | POST | ✅ | Stuck relay recovery cycle (v5.1.0+ / `$FK`) |
| `/relay/reset` | POST | ✅ | Relay contact-life health estimation reset (v5.1.0+ / `$FH`) |
| `/cabletemp` | GET, POST | ✅ | Cable temperature monitor configuration and status (v5.1.0+) |
| `/rfid/add` | POST | ✅ | RFID tag pairing mode (v4.0.0+) |
| `/rfid/users` | GET, POST, DELETE | ✅ | RFID tag to user mappings (v5.0.0+) |

✅ = Fully Supported \| ⚠️ = Partial Support \| ❌ = Not yet implemented

## License

This project is licensed under the Apache-2.0 License.
