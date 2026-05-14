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
from openevsehttp import OpenEVSE

async def main():
    # Initialize the charger
    charger = OpenEVSE("192.168.1.30")

    # Update state
    await charger.update()

    print(f"Charger State: {charger.status}")
    print(f"Current Charge: {charger.charge_current}A")

    # Toggle the Shaper feature
    if charger.shaper_active:
        print("Shaper is active, disabling...")
    else:
        print("Shaper is inactive, enabling...")

    await charger.toggle_shaper()

    # Clean up
    await charger.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Roadmap & Missing Features

Based on the latest OpenEVSE ESP32 firmware, future updates may include:
- Dedicated **`/time`** management.
- **`/logs`** retrieval for diagnostics.
- **`/emeter`** resets.
- Advanced **Schedule Planning** visualization.

## License

This project is licensed under the Apache-2.0 License.
