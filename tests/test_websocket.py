"""Tests for OpenEVSE Websocket."""

import asyncio
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
    async with aiohttp.ClientSession() as session:
        client = OpenEVSEWebsocket(SERVER_URL, mock_callback, session=session)
        yield client
        await client.close()


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
    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    # Define an async generator to simulate the WebSocket stream
    async def async_iter():
        yield msg

    mock_ws.__aiter__.side_effect = async_iter

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws),
        patch("asyncio.sleep", return_value=None),
    ):
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

    with (
        patch("aiohttp.ClientSession.ws_connect", side_effect=error),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
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
    async with aiohttp.ClientSession() as session:
        client = OpenEVSEWebsocket(
            SERVER_URL,
            callback,
            user="test",
            password="pw",
            session=session,
        )
        yield client
        await client.close()


@pytest.mark.asyncio
async def test_websocket_auth(ws_client_auth):
    """Test WebSocket connection with authentication."""
    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    # Use an async generator function for clean async iteration
    async def empty_iter():
        return
        yield

    mock_ws.__aiter__.side_effect = empty_iter

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws) as mock_connect,
        patch("asyncio.sleep", return_value=None),
    ):
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

    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    async def async_iter_closed():
        yield msg_closed

    mock_ws.__aiter__.side_effect = async_iter_closed

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws),
        patch("asyncio.sleep", return_value=None),
    ):
        await ws_client_auth.running()
        # Should stop running naturally on closed

    # 2. Test ERROR message
    msg_error = MagicMock()
    msg_error.type = aiohttp.WSMsgType.ERROR

    async def async_iter_error():
        yield msg_error

    mock_ws.__aiter__.side_effect = async_iter_error

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws),
        patch("asyncio.sleep", return_value=None),
    ):
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
    # Code sets state to STATE_DISCONNECTED on RuntimeError
    ws_client_auth._client.send_json.side_effect = RuntimeError("Runtime err")
    await ws_client_auth.keepalive()
    assert ws_client_auth.state == STATE_DISCONNECTED

    # Generic Exception
    # Code sets state to STATE_DISCONNECTED on generic Exception
    ws_client_auth._client.send_json.side_effect = Exception("Generic err")
    await ws_client_auth.keepalive()
    assert ws_client_auth.state == STATE_DISCONNECTED


@pytest.mark.asyncio
async def test_state_setter_no_callback(ws_client):
    """Test state setter without callback coverage."""
    ws_client.callback = None
    ws_client.state = STATE_STOPPED
    assert ws_client.state == STATE_STOPPED


@pytest.mark.asyncio
async def test_websocket_schedule_success_sync(ws_client):
    """Test state setter schedules the callback successfully when outside listener loop."""
    # Ensure no listener loop is set, so ensure_future path is taken
    ws_client._listener_loop = None

    # Trigger state change, which schedules callback
    ws_client.state = STATE_CONNECTED

    # We should have scheduled 1 task
    assert len(ws_client._tasks) == 1

    # Let the loop run to execute the callback
    await asyncio.gather(*ws_client._tasks)

    ws_client.callback.assert_called_with(
        SIGNAL_CONNECTION_STATE, STATE_CONNECTED, None
    )
    assert len(ws_client._tasks) == 0


@pytest.mark.asyncio
async def test_websocket_sync_callback(ws_client):
    """Test state setter with a synchronous callback."""
    # MagicMock is not awaitable, so it triggers the return at line 73.
    sync_callback = MagicMock(return_value=None)
    ws_client.callback = sync_callback
    ws_client.state = STATE_CONNECTED
    assert ws_client.state == STATE_CONNECTED
    sync_callback.assert_called_once()
    assert ws_client._error_reason is None


@pytest.mark.asyncio
async def test_websocket_schedule_failure_sync(ws_client, mock_callback):
    """Test state setter handles RuntimeError during scheduling."""
    # Use AsyncMock to ensure it's awaitable and triggers the try...except block
    async_mock = AsyncMock()

    # Trigger RuntimeError in create_task
    with (
        patch("asyncio.ensure_future", side_effect=RuntimeError("No loop")),
        patch("openevsehttp.websocket._LOGGER") as mock_logger,
    ):
        ws_client.callback = async_mock
        ws_client.state = STATE_CONNECTED
        assert mock_logger.error.called
        assert (
            "Failed to schedule callback from sync context"
            in mock_logger.error.call_args[0][0]
        )


@pytest.mark.asyncio
async def test_websocket_schedule_failure_async(ws_client):
    """Test _schedule_task handles RuntimeError during create_task."""
    async_mock = AsyncMock()
    mock_coro = async_mock()

    with (
        patch("asyncio.ensure_future", side_effect=RuntimeError("Failed")),
        patch("openevsehttp.websocket._LOGGER") as mock_logger,
    ):
        ws_client._schedule_task(mock_coro)
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_websocket_async_sync_callback(ws_client):
    """Test _set_state and running with a synchronous callback."""
    sync_callback = MagicMock(return_value=None)
    ws_client.callback = sync_callback

    # Test _set_state
    await ws_client._set_state(STATE_CONNECTED)
    sync_callback.assert_called_with(SIGNAL_CONNECTION_STATE, STATE_CONNECTED, None)

    # Test running with data
    sync_callback.reset_mock()
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.json.return_value = {"key": "value"}

    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    async def async_iter():
        yield msg

    mock_ws.__aiter__.side_effect = async_iter

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws),
        patch("asyncio.sleep", return_value=None),
    ):
        await ws_client.running()
        sync_callback.assert_any_call("data", {"key": "value"}, None)


@pytest.mark.asyncio
async def test_websocket_pong_handling(ws_client_auth):
    """Test handling of PONG messages."""
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.json.return_value = {"pong": 1}

    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    async def async_iter():
        yield msg

    mock_ws.__aiter__.side_effect = async_iter
    initial_pong = datetime.datetime.now() - datetime.timedelta(minutes=1)
    ws_client_auth._pong = initial_pong

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws),
        patch("asyncio.sleep", return_value=None),
    ):
        await ws_client_auth.running()
        assert ws_client_auth._pong > initial_pong


@pytest.mark.asyncio
async def test_websocket_stop_loop_break(ws_client_auth):
    """Test that setting state to STOPPED breaks the message loop."""
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.json.return_value = {"key": "value"}

    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    async def async_iter():
        yield msg
        ws_client_auth.state = STATE_STOPPED
        yield msg  # Should not be processed in loop due to break

    mock_ws.__aiter__.side_effect = async_iter

    with (
        patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws),
        patch("asyncio.sleep", return_value=None),
    ):
        await ws_client_auth.running()
        # Callback should be called for data before STOPPED
        assert (
            ws_client_auth.callback.call_count == 4
        )  # STARTING, CONNECTED, data, STOPPED


@pytest.mark.asyncio
async def test_websocket_listen(ws_client_auth):
    """Test the listen() method."""
    captured_loop = None

    async def mock_run_impl():
        nonlocal captured_loop
        captured_loop = ws_client_auth._listener_loop
        ws_client_auth._state = STATE_STOPPED

    with patch.object(ws_client_auth, "running", side_effect=mock_run_impl) as mock_run:
        # We need to mock state to NOT be STOPPED initially
        ws_client_auth._state = STATE_DISCONNECTED

        await ws_client_auth.listen()
        mock_run.assert_called()
        assert captured_loop is not None


@pytest.mark.asyncio
async def test_websocket_requires_external_session(mock_callback):
    """Test websocket startup fails without an external session."""
    client = OpenEVSEWebsocket(SERVER_URL, mock_callback)
    with pytest.raises(
        RuntimeError,
        match="An aiohttp.ClientSession must be provided via the session argument.",
    ):
        await client._ensure_session()


@pytest.mark.asyncio
async def test_websocket_rejects_session_from_different_loop(mock_callback):
    """Test websocket startup fails if session is bound to a different event loop."""
    async with aiohttp.ClientSession() as session:
        client = OpenEVSEWebsocket(SERVER_URL, mock_callback, session=session)
        other_loop = asyncio.new_event_loop()
        try:
            with patch.object(session, "_loop", other_loop):
                with pytest.raises(
                    RuntimeError,
                    match="The aiohttp.ClientSession is bound to a different event loop.",
                ):
                    await client._ensure_session()
        finally:
            other_loop.close()


@pytest.mark.asyncio
async def test_websocket_close_external_session(mock_callback):
    """Test close() when an external session is provided."""
    async with aiohttp.ClientSession() as session:
        client = OpenEVSEWebsocket(SERVER_URL, mock_callback, session=session)

        mock_ws = AsyncMock()
        client._client = mock_ws

        await client.close()
        assert client.state == STATE_STOPPED
        assert client._client is None
        mock_ws.close.assert_called_once()
        # Session should NOT be closed
        assert not session.closed
        assert client.session == session


@pytest.mark.asyncio
async def test_websocket_state_task_management(ws_client):
    """Test task management in state setter."""
    # Ensure a loop is running
    asyncio.get_running_loop()

    # Trigger async task creation
    ws_client.state = STATE_CONNECTED
    assert ws_client.state == STATE_CONNECTED
    assert len(ws_client._tasks) == 1

    # Wait for task to complete
    await asyncio.gather(*ws_client._tasks)
    assert len(ws_client._tasks) == 0


@pytest.mark.asyncio
async def test_websocket_close_cancels_pending_tasks(ws_client):
    """Test close() cancels pending callback tasks."""
    # Trigger a task creation
    ws_client.state = STATE_CONNECTED
    assert len(ws_client._tasks) == 1

    # Close should cancel and drain tasks
    await ws_client.close()
    assert len(ws_client._tasks) == 0


@pytest.mark.asyncio
async def test_websocket_ssl_options(mock_callback):
    """Test OpenEVSEWebsocket SSL options and ws_connect parameter passing."""
    async with aiohttp.ClientSession() as session:
        # Default ssl_verify=True
        ws_default = OpenEVSEWebsocket(
            "https://openevse.test.tld/",
            mock_callback,
            session=session,
        )
        assert ws_default.ssl_verify is True
        assert ws_default.uri == "wss://openevse.test.tld/ws"

        # Explicit ssl_verify=False
        ws_no_verify = OpenEVSEWebsocket(
            "https://openevse.test.tld/",
            mock_callback,
            session=session,
            ssl_verify=False,
        )
        assert ws_no_verify.ssl_verify is False
        assert ws_no_verify.uri == "wss://openevse.test.tld/ws"

        # Mock ws_connect to check that it is called with ssl=False when ssl_verify=False
        mock_ws = AsyncMock()
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=None)

        async def empty_iter():
            return
            yield

        mock_ws.__aiter__.side_effect = empty_iter

        with patch(
            "aiohttp.ClientSession.ws_connect", return_value=mock_ws
        ) as mock_connect:
            await ws_no_verify.running()
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args.kwargs
            assert call_kwargs.get("ssl") is False

        # When ssl_verify=True, ws_connect should NOT pass ssl=False
        with patch(
            "aiohttp.ClientSession.ws_connect", return_value=mock_ws
        ) as mock_connect:
            await ws_default.running()
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args.kwargs
            assert "ssl" not in call_kwargs
