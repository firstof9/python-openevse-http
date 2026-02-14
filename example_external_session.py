"""Example of using python-openevse-http with an external aiohttp.ClientSession.

This demonstrates how to pass your own session to the library, which is useful when:
- You want to manage the session lifecycle yourself
- You need to share a session across multiple API clients
- You want to configure custom session settings (timeouts, connectors, etc.)
"""

import asyncio

import aiohttp

from openevsehttp.__main__ import OpenEVSE


async def example_with_external_session():
    """Example using an external session."""
    # Create your own session with custom settings
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Pass the session to OpenEVSE
        charger = OpenEVSE("openevse.local", session=session)

        # Use the charger normally
        await charger.update()
        print(f"Status: {charger.status}")
        print(f"Current: {charger.charging_current}A")

        # The session will be closed when the context manager exits
        # but OpenEVSE won't close it (since it's externally managed)
        await charger.ws_disconnect()


async def example_without_external_session():
    """Example without external session (backward compatible)."""
    # The library will create and manage its own sessions
    charger = OpenEVSE("openevse.local")

    # Use the charger normally
    await charger.update()
    print(f"Status: {charger.status}")
    print(f"Current: {charger.charging_current}A")

    await charger.ws_disconnect()


async def example_shared_session():
    """Example sharing a session between multiple clients."""
    async with aiohttp.ClientSession() as session:
        # Use the same session for multiple chargers
        charger1 = OpenEVSE("charger1.local", session=session)
        charger2 = OpenEVSE("charger2.local", session=session)

        # Both chargers use the same session
        await charger1.update()
        await charger2.update()

        print(f"Charger 1 Status: {charger1.status}")
        print(f"Charger 2 Status: {charger2.status}")

        await charger1.ws_disconnect()
        await charger2.ws_disconnect()


if __name__ == "__main__":
    # Run one of the examples
    asyncio.run(example_with_external_session())
