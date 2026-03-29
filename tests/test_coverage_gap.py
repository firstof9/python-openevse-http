"""Tests for remaining coverage gaps."""

import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import UnknownError
from openevsehttp.websocket import (
    STATE_CONNECTED,
    STATE_STOPPED,
    OpenEVSEWebsocket,
)
from tests.const import SERVER_URL

pytestmark = pytest.mark.asyncio


async def test_websocket_coverage_gaps():
    """Test remaining lines in websocket.py."""
    callback = AsyncMock()
    ws = OpenEVSEWebsocket(SERVER_URL, callback)

    # 1. Line 102: break when STATE_STOPPED
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.json.return_value = {"key": "value"}

    mock_ws = MagicMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    async def async_iter_stop():
        # Yield one message, then change state to STOPPED
        yield msg
        ws.state = STATE_STOPPED
        yield msg  # Should break before this is processed if we use it, 
                   # but the iterator loop itself checks state

    mock_ws.__aiter__.side_effect = async_iter_stop

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        # We need to ensure state is CONNECTED initially so the loop starts
        # but the code sets it to CONNECTED automatically in 'running'
        await ws.running()
        # Verify it broke early
        assert ws.state == STATE_STOPPED

    # 2. Line 109: "pong" in msg.keys()
    msg_pong = MagicMock()
    msg_pong.type = aiohttp.WSMsgType.TEXT
    msg_pong.json.return_value = {"pong": 1}

    async def async_iter_pong():
        yield msg_pong
        # Stop after one message
        ws.state = STATE_STOPPED

    mock_ws.__aiter__.side_effect = async_iter_pong
    ws.state = STATE_CONNECTED  # Reset state

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await ws.running()
        assert ws._pong is not None
        assert isinstance(ws._pong, datetime.datetime)

    # Clean up the session we created
    if ws.session and not ws.session.closed:
        await ws.session.close()


async def test_override_failure_logic():
    """Test 'ok: False' paths in override.py (direct coverage)."""
    with aioresponses() as m:
        # Initial status/config/override calls for update()
        m.get(f"http://{SERVER_URL}/status", status=200, body='{"status": "sleeping"}')
        m.get(f"http://{SERVER_URL}/config", status=200, body='{"version": "4.1.0"}')
        m.get(f"http://{SERVER_URL}/override", status=200, body='{"state": "disabled"}')

        charger = OpenEVSE(SERVER_URL)
        await charger.update()

        # 1. set() failure (Line 73-74)
        m.post(
            f"http://{SERVER_URL}/override",
            status=200, # or 500, doesn't matter as long as ok=False
            body='{"msg": "error", "ok": false}',
        )
        with pytest.raises(UnknownError):
            await charger.set_override(charge_current=16)

        # 2. toggle() failure (Line 88-89)
        m.patch(
            f"http://{SERVER_URL}/override",
            status=200,
            body='{"msg": "error", "ok": false}',
        )
        with pytest.raises(UnknownError):
            await charger.toggle_override()

        # 3. clear() failure (Line 111-112)
        m.delete(
            f"http://{SERVER_URL}/override",
            status=200,
            body='{"msg": "error", "ok": false}',
        )
        with pytest.raises(UnknownError):
            await charger.clear_override()
