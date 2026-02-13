# External Session Management

## Overview

The `python-openevse-http` library now supports passing an external `aiohttp.ClientSession` to the `OpenEVSE` class. This allows you to manage the session lifecycle yourself and share sessions across multiple API clients.

## Benefits

- **Session Reuse**: Share a single session across multiple OpenEVSE instances or other aiohttp-based clients
- **Custom Configuration**: Configure session settings like timeouts, connectors, and SSL verification
- **Resource Management**: Better control over connection pooling and resource cleanup
- **Integration**: Easier integration with existing applications that already manage aiohttp sessions

## Usage

### With External Session

```python
import aiohttp
from openevsehttp import OpenEVSE

async def main():
    # Create your own session with custom settings
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Pass the session to OpenEVSE
        charger = OpenEVSE("openevse.local", session=session)
        
        # Use the charger normally
        await charger.update()
        print(f"Status: {charger.status}")
        
        # Clean up
        await charger.ws_disconnect()
        # Session will be closed by the context manager
```

### Without External Session (Backward Compatible)

```python
from openevsehttp import OpenEVSE

async def main():
    # The library creates and manages its own sessions
    charger = OpenEVSE("openevse.local")
    
    # Use the charger normally
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
        # Use the same session for multiple chargers
        charger1 = OpenEVSE("charger1.local", session=session)
        charger2 = OpenEVSE("charger2.local", session=session)
        
        # Both chargers use the same session
        await charger1.update()
        await charger2.update()
        
        await charger1.ws_disconnect()
        await charger2.ws_disconnect()
```

## API Changes

### OpenEVSE.__init__()

```python
def __init__(
    self,
    host: str,
    user: str = "",
    pwd: str = "",
    session: aiohttp.ClientSession | None = None,
) -> None:
```

**Parameters:**
- `host` (str): The hostname or IP address of the OpenEVSE charger
- `user` (str, optional): Username for authentication
- `pwd` (str, optional): Password for authentication
- `session` (aiohttp.ClientSession | None, optional): External session to use for HTTP requests. If not provided, the library will create temporary sessions as needed.

### OpenEVSEWebsocket.__init__()

```python
def __init__(
    self,
    server,
    callback,
    user=None,
    password=None,
    session: aiohttp.ClientSession | None = None,
):
```

**Parameters:**
- `server`: The server URL
- `callback`: Callback function for websocket events
- `user` (optional): Username for authentication
- `password` (optional): Password for authentication
- `session` (aiohttp.ClientSession | None, optional): External session to use for websocket connections. If not provided, a new session will be created.

## Important Notes

1. **Session Lifecycle**: When you provide an external session, you are responsible for closing it. The library will NOT close externally provided sessions.

2. **Backward Compatibility**: This change is fully backward compatible. Existing code that doesn't provide a session will continue to work exactly as before.

3. **Websocket Sessions**: The websocket connection will also use the provided session, ensuring consistent session management across all HTTP and WebSocket operations.

4. **Thread Safety**: If you're using the same session across multiple OpenEVSE instances, ensure you're following aiohttp's thread safety guidelines.

## Migration Guide

If you want to migrate existing code to use external sessions:

**Before:**
```python
charger = OpenEVSE("openevse.local")
await charger.update()
```

**After:**
```python
async with aiohttp.ClientSession() as session:
    charger = OpenEVSE("openevse.local", session=session)
    await charger.update()
```

No other changes are required!
