# HTTP Session Management

## Overview

The `python-openevse-http` library requires you to pass an external `aiohttp.ClientSession` to `OpenEVSE`. Session ownership stays with the caller, so the library no longer constructs temporary HTTP clients internally.

## Benefits

- **Session Reuse**: Share a single session across multiple OpenEVSE instances or other `aiohttp` clients
- **Custom Configuration**: Configure timeouts, connectors, proxies, and SSL behavior yourself
- **Resource Management**: Keep connection pooling and cleanup in one place
- **Predictable Lifecycle**: Avoid hidden session creation inside request and websocket code paths

## Usage

### Basic Usage

```python
import aiohttp
from openevsehttp import OpenEVSE

async def main():
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        charger = OpenEVSE("openevse.local", session=session)
        await charger.update()
        print(f"Status: {charger.status}")
        await charger.ws_disconnect()
```

### Sharing a Session

```python
import aiohttp
from openevsehttp import OpenEVSE

async def main():
    async with aiohttp.ClientSession() as session:
        charger1 = OpenEVSE("charger1.local", session=session)
        charger2 = OpenEVSE("charger2.local", session=session)

        await charger1.update()
        await charger2.update()
```

### Websocket Startup

Start websocket listening from the same event loop that owns the
`aiohttp.ClientSession`:

```python
import aiohttp
from openevsehttp import OpenEVSE

async def main():
    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE("openevse.local", session=session)
        await charger.ws_start()
        await charger.ws_disconnect()
```

`ws_start()` is async so websocket tasks are created on the event loop that owns
the configured `aiohttp.ClientSession`. This prevents using a session from a
private background loop it was not created on.

## API Notes

- `OpenEVSE(..., session=session)` uses the provided session for HTTP requests.
- `OpenEVSEWebsocket(..., session=session)` uses the provided session for websocket connections.
- If no session is configured, HTTP requests and websocket startup raise `RuntimeError`.
- Call `await charger.ws_start()` from the event loop that owns the session.
- Externally provided sessions are never closed by the library.

## Migration

Before:

```python
charger = OpenEVSE("openevse.local")
await charger.update()
```

After:

```python
import aiohttp

async with aiohttp.ClientSession() as session:
    charger = OpenEVSE("openevse.local", session=session)
    await charger.update()
```
