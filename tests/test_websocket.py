"""Tests for OpenEVSE Websocket."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import pytest_asyncio

from openevsehttp.websocket import (
    ERROR_AUTH_FAILURE,
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STARTING,
    STATE_STOPPED,
    OpenEVSEWebsocket,
)

SERVER_URL = "http://openevse.test.tld/"


@pytest.fixture
def mock_callback():
    """Mock callback fixture."""
    return AsyncMock()


@pytest_asyncio.fixture
async def ws_client(mock_callback):
    """Websocket client fixture."""
    # Making this fixture async ensures an event loop is running when
    # OpenEVSEWebsocket initializes aiohttp.ClientSession
    client = OpenEVSEWebsocket(SERVER_URL, mock_callback)
    yield client
    # Clean up session to prevent unclosed session warnings
    if client.session and not client.session.closed:
        await client.session.close()


def test_get_uri():
    """Test URI generation."""
    # Standard URL with trailing slash
    assert OpenEVSEWebsocket._get_uri("http://test.com/") == "ws://test.com/ws"
    # URL with endpoint
    assert OpenEVSEWebsocket._get_uri("http://test.com/status") == "ws://test.com/ws"
    # HTTPS conversion
    assert OpenEVSEWebsocket._get_uri("https://test.com/") == "wss://test.com/ws"


@pytest.mark.asyncio
async def test_run_success(ws_client, mock_callback):
    """Test successful run cycle."""
    # Mock message
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.json.return_value = {"key": "value"}

    # Mock context manager and iterator
    mock_ws = MagicMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    # Define an async generator to simulate the WebSocket stream
    async def async_iter():
        yield msg

    mock_ws.__aiter__.side_effect = async_iter

    with patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws):
        await ws_client.running()

        # Check that state transitions and data callbacks occurred
        mock_callback.assert_any_call(SIGNAL_CONNECTION_STATE, STATE_STARTING, None)
        mock_callback.assert_any_call(SIGNAL_CONNECTION_STATE, STATE_CONNECTED, None)
        mock_callback.assert_any_call("data", {"key": "value"}, None)


@pytest.mark.asyncio
async def test_auth_failure(ws_client, mock_callback):
    """Test authentication failure handling."""
    error = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=MagicMock(), status=401
    )

    with patch("aiohttp.ClientSession.ws_connect", side_effect=error):
        await ws_client.running()

        assert ws_client.state == STATE_STOPPED
        mock_callback.assert_called_with(
            SIGNAL_CONNECTION_STATE, STATE_STOPPED, ERROR_AUTH_FAILURE
        )


@pytest.mark.asyncio
async def test_connection_error_retry(ws_client, mock_callback):
    """Test connection retry logic."""
    error = aiohttp.ClientConnectionError("Connection lost")

    with patch("aiohttp.ClientSession.ws_connect", side_effect=error), patch(
        "asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        # Simulate one run of 'running' which catches the error and triggers sleep
        await ws_client.running()

        assert ws_client.failed_attempts == 1
        assert ws_client.state == STATE_DISCONNECTED
        mock_sleep.assert_called()


@pytest.mark.asyncio
async def test_max_retries(ws_client, mock_callback):
    """Test max retries reached."""
    ws_client.failed_attempts = 6  # MAX_FAILED_ATTEMPTS is 5
    error = aiohttp.ClientConnectionError("Connection lost")

    with patch("aiohttp.ClientSession.ws_connect", side_effect=error):
        await ws_client.running()

        assert ws_client.state == STATE_STOPPED


@pytest.mark.asyncio
async def test_keepalive(ws_client):
    """Test keepalive sending ping."""
    ws_client._client = AsyncMock()
    ws_client._ping = datetime.datetime.now()
    ws_client._pong = datetime.datetime.now()

    await ws_client.keepalive()
    ws_client._client.send_json.assert_called_with({"ping": 1})


@pytest.mark.asyncio
async def test_keepalive_timeout(ws_client, mock_callback):
    """Test keepalive detecting timeout (missing pong)."""
    ws_client._client = AsyncMock()
    now = datetime.datetime.now()

    # Simulate ping sent 10s ago, but last pong was 20s ago (older than ping)
    ws_client._ping = now
    ws_client._pong = now - datetime.timedelta(seconds=10)

    await ws_client.keepalive()

    mock_callback.assert_called_with(
        SIGNAL_CONNECTION_STATE, STATE_DISCONNECTED, "No pong reply"
    )


@pytest_asyncio.fixture
async def ws_client_auth():
    """Fixture for authenticated websocket client."""
    callback = AsyncMock()
    client = OpenEVSEWebsocket(
        f"http://{SERVER_URL}", callback, user="test", password="pw"
    )
    yield client
    if client.session and not client.session.closed:
        await client.session.close()


@pytest.mark.asyncio
async def test_websocket_auth(ws_client_auth):
    """Test WebSocket connection with authentication."""
    mock_ws = MagicMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    # Use an async generator function for clean async iteration
    async def empty_iter():
        if False:
            yield

    mock_ws.__aiter__.side_effect = empty_iter

    with patch(
        "aiohttp.ClientSession.ws_connect", return_value=mock_ws
    ) as mock_connect:
        await ws_client_auth.running()

        # Verify BasicAuth was created and passed
        call_args = mock_connect.call_args
        assert "auth" in call_args.kwargs
        assert isinstance(call_args.kwargs["auth"], aiohttp.BasicAuth)
        assert call_args.kwargs["auth"].login == "test"
        assert call_args.kwargs["auth"].password == "pw"


@pytest.mark.asyncio
async def test_websocket_message_types(ws_client_auth):
    """Test CLOSED and ERROR message types."""
    # 1. Test CLOSED message
    msg_closed = MagicMock()
    msg_closed.type = aiohttp.WSMsgType.CLOSED

    mock_ws = MagicMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    async def async_iter_closed():
        yield msg_closed

    mock_ws.__aiter__.side_effect = async_iter_closed

    with patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws):
        await ws_client_auth.running()
        # Should stop running naturally on closed

    # 2. Test ERROR message
    msg_error = MagicMock()
    msg_error.type = aiohttp.WSMsgType.ERROR

    async def async_iter_error():
        yield msg_error

    mock_ws.__aiter__.side_effect = async_iter_error

    with patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws):
        await ws_client_auth.running()
        # Should stop running on error


@pytest.mark.asyncio
async def test_websocket_exceptions_generic(ws_client_auth):
    """Test generic exception during run."""
    with patch("aiohttp.ClientSession.ws_connect", side_effect=Exception("Boom")):
        await ws_client_auth.running()
        assert ws_client_auth.state == STATE_STOPPED


@pytest.mark.asyncio
async def test_websocket_unexpected_response_error(ws_client_auth):
    """Test unexpected client response error."""
    # Status 500 triggers the "else" block in the exception handler
    error = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=MagicMock(), status=500
    )

    with patch("aiohttp.ClientSession.ws_connect", side_effect=error):
        await ws_client_auth.running()

        # We cannot assert ws_client_auth._error_reason because the state setter clears it.
        # Instead, we assert that the callback was called with the correct error.
        ws_client_auth.callback.assert_called_with(
            SIGNAL_CONNECTION_STATE, STATE_STOPPED, error
        )


@pytest.mark.asyncio
async def test_keepalive_client_missing(ws_client_auth):
    """Test keepalive when client is None."""
    ws_client_auth._client = None
    # Should log warning but not crash
    await ws_client_auth.keepalive()


@pytest.mark.asyncio
async def test_keepalive_send_exceptions(ws_client_auth):
    """Test exceptions during keepalive send."""
    ws_client_auth._client = AsyncMock()

    # TypeError
    ws_client_auth._client.send_json.side_effect = TypeError("Type err")
    await ws_client_auth.keepalive()

    # ValueError
    ws_client_auth._client.send_json.side_effect = ValueError("Value err")
    await ws_client_auth.keepalive()

    # RuntimeError
    # Code sets state to STATE_DISCONNECTED on RuntimeError (line 172)
    ws_client_auth._client.send_json.side_effect = RuntimeError("Runtime err")
    await ws_client_auth.keepalive()
    assert ws_client_auth.state == STATE_DISCONNECTED

    # Generic Exception
    # Code sets state to STATE_DISCONNECTED on generic Exception (line 175)
    ws_client_auth._client.send_json.side_effect = Exception("Generic err")
    await ws_client_auth.keepalive()
    assert ws_client_auth.state == STATE_DISCONNECTED
