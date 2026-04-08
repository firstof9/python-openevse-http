"""Tests for core client infrastructure (HTTP, websocket, auth, version, firmware)."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import aiohttp
import pytest
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from aiohttp.client_reqrep import ConnectionKey
from awesomeversion.exceptions import AwesomeVersionCompareException

import openevsehttp.__main__ as main
from openevsehttp import OpenEVSE as PublicOpenEVSE
from openevsehttp.__main__ import OpenEVSE
from openevsehttp.const import (
    UPDATE_TRIGGERS,
)
from openevsehttp.exceptions import (
    AlreadyListening,
    AuthenticationError,
    MissingMethod,
    MissingSerial,
    ParseJSONError,
)
from openevsehttp.websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STOPPED,
    OpenEVSEWebsocket,
)
from tests.common import load_fixture

pytestmark = pytest.mark.asyncio

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_RAPI = "http://openevse.test.tld/r"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_URL_WS = "ws://openevse.test.tld/ws"
TEST_URL_GITHUB_v4 = (
    "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest"
)
TEST_URL_GITHUB_v2 = (
    "https://api.github.com/repos/OpenEVSE/ESP8266_WiFi_v2.x/releases/latest"
)
SERVER_URL = "openevse.test.tld"
DUMMY_PWD = "fakepassword"


# ── Auth / update / status ────────────────────────────────────────────


async def test_public_api_export():
    """Verify OpenEVSE is exported from the package root."""
    assert PublicOpenEVSE is not None
    assert PublicOpenEVSE is OpenEVSE


async def test_get_status_auth(test_charger_auth):
    """Test authenticated status update."""
    await test_charger_auth.update()
    status = test_charger_auth.status
    assert status == "sleeping"
    await test_charger_auth.ws_disconnect()


async def test_ws_state(test_charger):
    """Test websocket state transitions."""
    await test_charger.update()
    assert test_charger.ws_state == STATE_STOPPED
    with patch("openevsehttp.client.OpenEVSEWebsocket.listen", AsyncMock()):
        test_charger.ws_start()
        value = test_charger.ws_state
        assert value == STATE_DISCONNECTED
        await test_charger.ws_disconnect()
        assert test_charger.ws_state == STATE_STOPPED


async def test_update_status(test_charger):
    """Test internal _update_status method."""
    data = json.loads(load_fixture("v4_json/status.json"))
    await test_charger._update_status("data", data, None)
    assert test_charger._status == data


async def test_update_non_dict(mock_aioclient, caplog):
    """Test update() handles non-dict responses for status and config."""
    # Use a unique host to avoid hitting mocks from conftest.py
    unique_host = "non-dict.test.tld"
    test_charger = OpenEVSE(unique_host)
    url_status = f"http://{unique_host}/status"
    url_config = f"http://{unique_host}/config"

    # Test /status returning a string
    mock_aioclient.get(url_status, status=200, body="not a json")
    mock_aioclient.get(url_config, status=200, body=json.dumps({"wifi_serial": "123"}))

    with caplog.at_level(logging.WARNING):
        await test_charger.update()
    assert "Received non-JSON response from /status: not a json" in caplog.text

    # Test /config returning a string
    caplog.clear()
    mock_aioclient.get(url_status, status=200, body=json.dumps({"state": "sleeping"}))
    mock_aioclient.get(url_config, status=200, body="not a json")

    with caplog.at_level(logging.WARNING):
        await test_charger.update()
    assert "Received non-JSON response from /config: not a json" in caplog.text


async def test_get_status_auth_err(test_charger_auth_err):
    """Test status update with authentication failure."""
    with pytest.raises(main.AuthenticationError):
        await test_charger_auth_err.update()


# ── send_command ──────────────────────────────────────────────────────


async def test_send_command(test_charger, mock_aioclient):
    """Test sending a RAPI command."""
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == ("OK", "$OK^20")


async def test_send_command_failed(test_charger, mock_aioclient):
    """Test sending a RAPI command with failed response."""
    value = {"cmd": "OK", "ret": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == ("OK", "$NK^21")


async def test_send_command_missing(test_charger, mock_aioclient):
    """Test v4 Status reply with missing 'ret'."""
    value = {"cmd": "OK", "what": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == (False, "")


async def test_send_command_missing_cmd(test_charger, mock_aioclient):
    """Test v4 Status reply with missing 'cmd'."""
    value = {"ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == (False, "")


async def test_send_command_auth(test_charger_auth, mock_aioclient):
    """Test authenticated RAPI command."""
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger_auth.send_command("test")
    assert status == ("OK", "$OK^20")


async def test_send_command_parse_err(test_charger_auth, mock_aioclient):
    """Test RAPI command with JSON parse error."""
    mock_aioclient.post(
        TEST_URL_RAPI, status=400, body='{"msg": "Could not parse JSON"}'
    )
    with pytest.raises(main.ParseJSONError):
        await test_charger_auth.send_command("test")

    mock_aioclient.post(
        TEST_URL_RAPI, status=400, body='{"error": "Could not parse JSON"}'
    )
    with pytest.raises(main.ParseJSONError):
        await test_charger_auth.send_command("test")

    mock_aioclient.post(TEST_URL_RAPI, status=400, body='{"other": "Something else"}')
    with pytest.raises(main.ParseJSONError):
        await test_charger_auth.send_command("test")

    mock_aioclient.post(TEST_URL_RAPI, status=400, body='"Just a string response"')
    with pytest.raises(main.ParseJSONError):
        await test_charger_auth.send_command("test")


async def test_send_command_auth_err(test_charger_auth, mock_aioclient):
    """Test RAPI command with authentication failure."""
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=401,
    )
    with pytest.raises(main.AuthenticationError):
        await test_charger_auth.send_command("test")


async def test_send_command_async_timeout(test_charger_auth, mock_aioclient, caplog):
    """Test RAPI command with async timeout."""
    mock_aioclient.post(
        TEST_URL_RAPI,
        exception=TimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(TimeoutError):
            await test_charger_auth.send_command("test")
    assert main.ERROR_TIMEOUT in caplog.text


async def test_send_command_server_timeout(test_charger_auth, mock_aioclient, caplog):
    """Test RAPI command with server timeout."""
    mock_aioclient.post(
        TEST_URL_RAPI,
        exception=ServerTimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(main.ServerTimeoutError):
            await test_charger_auth.send_command("test")
    assert f"{main.ERROR_TIMEOUT}: {TEST_URL_RAPI}" in caplog.text


# ── test_and_get / identify ──────────────────────────────────────────


async def test_test_and_get(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test test_and_get (identify) method."""
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )
    data = await test_charger.test_and_get()
    assert data["serial"] == "1234567890AB"
    assert data["model"] == "unknown"

    with pytest.raises(MissingSerial):
        with caplog.at_level(logging.DEBUG):
            data = await test_charger_v2.test_and_get()
    assert "Older firmware detected, missing serial." in caplog.text


async def test_identify_with_buildenv(mock_aioclient):
    """Test test_and_get method (identify) with buildenv in response."""
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"wifi_serial": "123", "buildenv": "esp32"}',
    )
    charger = OpenEVSE(SERVER_URL)
    data = await charger.test_and_get()
    assert data["model"] == "esp32"


# ── firmware_check ───────────────────────────────────────────────────


async def test_firmware_check(
    test_charger,
    test_charger_dev,
    test_charger_v2,
    test_charger_broken,
    test_charger_broken_semver,
    test_charger_unknown_semver,
    mock_aioclient,
    caplog,
):
    """Test firmware check functionality."""
    await test_charger.update()
    mock_aioclient.get(
        TEST_URL_GITHUB_v4,
        status=200,
        body=load_fixture("github_v4.json"),
    )
    firmware = await test_charger.firmware_check()
    assert firmware["latest_version"] == "4.1.4"

    mock_aioclient.get(
        TEST_URL_GITHUB_v4,
        status=404,
        body="",
    )
    firmware = await test_charger.firmware_check()
    assert firmware is None

    mock_aioclient.get(
        TEST_URL_GITHUB_v4,
        exception=aiohttp.ClientConnectorError(
            ConnectionKey("localhost", 80, False, None, None, None, None),
            OSError(ConnectionError),
        ),
    )
    with caplog.at_level(logging.DEBUG):
        firmware = await test_charger.firmware_check()
        assert (
            f"Cannot connect to host localhost:80 ssl:None [None] : {TEST_URL_GITHUB_v4}"
            in caplog.text
        )
    assert firmware is None

    await test_charger_dev.update()
    mock_aioclient.get(
        TEST_URL_GITHUB_v4,
        status=200,
        body=load_fixture("github_v4.json"),
    )
    with caplog.at_level(logging.DEBUG):
        firmware = await test_charger_dev.firmware_check()
    assert "Stripping 'dev' from version." in caplog.text
    assert firmware["latest_version"] == "4.1.4"

    await test_charger_v2.update()
    mock_aioclient.get(
        TEST_URL_GITHUB_v2,
        status=200,
        body=load_fixture("github_v2.json"),
    )
    firmware = await test_charger_v2.firmware_check()
    assert firmware["latest_version"] == "2.9.1"

    await test_charger_broken.update()
    mock_aioclient.get(
        TEST_URL_GITHUB_v4,
        status=200,
        body=load_fixture("github_v4.json"),
    )
    with caplog.at_level(logging.DEBUG):
        firmware = await test_charger_broken.firmware_check()
    assert "Unable to find firmware version." in caplog.text
    assert firmware is None

    await test_charger_broken_semver.update()
    mock_aioclient.get(
        TEST_URL_GITHUB_v4,
        status=200,
        body=load_fixture("github_v4.json"),
    )
    firmware = await test_charger_broken_semver.firmware_check()
    assert firmware["latest_version"] == "4.1.4"

    await test_charger_unknown_semver.update()
    assert test_charger_unknown_semver.wifi_firmware == "random_a4f11e"
    mock_aioclient.get(
        TEST_URL_GITHUB_v4,
        status=200,
        body=load_fixture("github_v4.json"),
    )
    with caplog.at_level(logging.DEBUG):
        firmware = await test_charger_unknown_semver.firmware_check()
        assert "Using version: random_a4f11e" in caplog.text
        assert "Non-semver firmware version detected." in caplog.text
        assert firmware is None


async def test_firmware_check_no_config():
    """Test firmware_check when config is not loaded."""
    charger = OpenEVSE(SERVER_URL)

    result = await charger.firmware_check()

    assert result is None


async def test_firmware_check_no_firmware_version(mock_aioclient):
    """Test firmware_check when firmware_version is missing."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body="{}",
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body='{"hostname": "openevse"}',
    )

    charger = OpenEVSE(SERVER_URL)
    await charger.update()

    result = await charger.firmware_check()

    assert result is None


async def test_firmware_check_github_api_error(mock_aioclient):
    """Test firmware_check when GitHub API fails."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )
    mock_aioclient.get(
        "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest",
        status=404,
        body='{"error": "Not found"}',
    )

    charger = OpenEVSE(SERVER_URL)
    await charger.update()

    result = await charger.firmware_check()

    # Should return None when GitHub API fails
    assert result is None


async def test_firmware_check_external_session(mock_aioclient):
    """Test firmware_check with an external session."""
    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body='{"version": "4.0.1", "wifi_serial": "123"}',
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"hostname": "test", "version": "4.0.1"}',
    )
    mock_aioclient.get(
        "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest",
        status=200,
        body='{"tag_name": "v4.1.0", "body": "notes", "html_url": "http://github"}',
    )

    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)
        await charger.update()
        # Ensure version is set in config
        charger._config["version"] = "4.0.1"
        result = await charger.firmware_check()
        assert result["latest_version"] == "v4.1.0"


async def test_firmware_check_errors(mock_aioclient):
    """Test firmware_check error paths."""
    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body='{"version": "4.0.1", "wifi_serial": "123"}',
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"hostname": "test", "version": "4.0.1"}',
    )

    url = "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest"

    # Status 404 from github
    mock_aioclient.get(url, status=404)

    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)
        await charger.update()
        charger._config["version"] = "4.0.1"
        assert await charger.firmware_check() is None

    # Timeout from github
    mock_aioclient.get(url, exception=asyncio.TimeoutError())
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "4.0.1"
    assert await charger.firmware_check() is None

    # ContentTypeError from github

    mock_aioclient.get(
        url, exception=ContentTypeError(MagicMock(), MagicMock(), message="test")
    )
    assert await charger.firmware_check() is None

    # JSONDecodeError from github
    mock_aioclient.get(url, status=200, body="not json")
    assert await charger.firmware_check() is None

    # Non-dict JSON from github
    mock_aioclient.get(url, status=200, body='"just a string"')
    assert await charger.firmware_check() is None


# ── version_check ────────────────────────────────────────────────────


async def test_version_check(test_charger_new, mock_aioclient, caplog):
    """Test version check function."""
    await test_charger_new.update()

    result = test_charger_new._version_check("4.0.0")
    assert result

    result = test_charger_new._version_check("4.0.0", "4.1.7")
    assert not result

    # Test multi-digit version components (e.g. 4.10.0)
    test_charger_new._config["version"] = "v4.10.0"
    result = test_charger_new._version_check("4.9.0")
    assert result
    result = test_charger_new._version_check("4.11.0")
    assert not result


async def test_version_check_exceptions():
    """Test _version_check exception paths."""
    charger = OpenEVSE(SERVER_URL)

    # Invalid version string should log warning and return False
    charger._config = {"version": "invalid"}
    # _version_check catches AwesomeVersionCompareException and returns False
    assert charger._version_check("2.0.0") is False

    # Trigger AwesomeVersionCompareException in limit comparison

    with patch(
        "awesomeversion.AwesomeVersion.__le__",
        side_effect=AwesomeVersionCompareException,
    ):
        charger._config = {"version": "2.9.1"}
        assert charger._version_check("2.0.0", "3.0.0") is False

    # Trigger AwesomeVersionCompareException in GE comparison
    with patch(
        "awesomeversion.AwesomeVersion.__ge__",
        side_effect=AwesomeVersionCompareException,
    ):
        charger._config = {"version": "2.9.1"}
        assert charger._version_check("2.0.0") is False


async def test_version_check_master():
    """Test _version_check with 'master' in version."""
    charger = OpenEVSE(SERVER_URL)
    charger._config = {"version": "v4.0.1.master"}
    # This should set value to "dev"
    assert charger._version_check("2.0.0") is True


async def test_version_check_limit():
    """Test _version_check with max_version."""
    charger = OpenEVSE(SERVER_URL)
    charger._config = {"version": "2.9.1"}
    assert charger._version_check("2.0.0", "3.0.0") is True
    assert charger._version_check("3.0.0", "4.0.0") is False

    # Test the wrapper
    assert charger.version_check("2.0.0") is True


# ── websocket lifecycle ──────────────────────────────────────────────


async def test_websocket_functions(test_charger, mock_aioclient, caplog):
    """Test websocket lifecycle methods."""
    mock_aioclient.get(
        TEST_URL_WS,
        status=200,
        body=load_fixture("websocket.json"),
    )
    await test_charger.update()
    with patch("openevsehttp.client.OpenEVSEWebsocket.listen", AsyncMock()):
        test_charger.ws_start()
        await test_charger.ws_disconnect()


async def test_ws_start_already_listening():
    """Test ws_start raises AlreadyListening if already listening."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.state = "connected"
    charger._ws_listening = True

    with pytest.raises(AlreadyListening):
        charger.ws_start()


async def test_ws_start_reset_listening():
    """Test ws_start resets _ws_listening if websocket is not connected."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.state = "disconnected"
    charger._ws_listening = True

    with patch.object(charger, "_start_listening"):
        with pytest.raises(AlreadyListening):
            charger.ws_start()


async def test_start_listening_no_loop():
    """Test _start_listening when no running loop is found."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    # Mock calls to return coroutines for create_task
    charger.websocket.listen.return_value = asyncio.Future()
    charger.websocket.listen.return_value.set_result(None)
    charger.repeat = MagicMock()

    with patch("asyncio.get_running_loop", side_effect=RuntimeError):
        with patch("asyncio.new_event_loop") as mock_new_loop:
            mock_loop = MagicMock()
            mock_new_loop.return_value = mock_loop
            with patch("threading.Thread") as mock_thread:
                # Mock repeat and listen to return None to avoid unawaited coroutines
                # as the mock loop won't actually run them.
                with (
                    patch.object(charger, "repeat", return_value=None),
                    patch.object(charger.websocket, "listen", return_value=None),
                ):
                    charger._start_listening()
                    assert charger._loop == mock_loop
                    mock_thread.assert_called_once()


async def test_update_status_states():
    """Test _update_status with different websocket states."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.uri = "ws://test"

    # Test connected
    await charger._update_status(SIGNAL_CONNECTION_STATE, STATE_CONNECTED, None)
    assert charger._ws_listening is True

    # Test disconnected
    await charger._update_status(
        SIGNAL_CONNECTION_STATE, STATE_DISCONNECTED, "test error"
    )
    assert charger._ws_listening is False

    # Test stopped with error
    await charger._update_status(SIGNAL_CONNECTION_STATE, STATE_STOPPED, "fatal error")
    assert charger._ws_listening is False


async def test_update_status_data_triggers(mock_aioclient):
    """Test _update_status with data that triggers update and callback."""
    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body='{"version": "4.0.1"}',
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"hostname": "test"}',
    )

    charger = OpenEVSE(SERVER_URL)

    # Set a coroutine callback
    async def mock_callback_coro():
        pass

    mock_callback = AsyncMock(side_effect=mock_callback_coro)
    charger.callback = mock_callback

    # "wh" should be popped to "watthour"
    # "config_version" is in UPDATE_TRIGGERS
    data = {"wh": 100, "config_version": 2}
    await charger._update_status("data", data, None)

    assert data["watthour"] == 100
    assert "wh" not in data
    assert charger._status["watthour"] == 100
    mock_callback.assert_called_once()

    # Test non-coroutine callback
    charger.callback = MagicMock()
    await charger._update_status("data", {"test": 1}, None)
    charger.callback.assert_called_once()


async def test_repeat():
    """Test repeat helper."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    # Mock ws_state to stop after one iteration
    with patch(
        "openevsehttp.__main__.OpenEVSE.ws_state", new_callable=PropertyMock
    ) as mock_state:
        mock_state.side_effect = ["connected", "stopped"]

        mock_func = AsyncMock()
        with patch("asyncio.sleep", AsyncMock()):
            await charger.repeat(1, mock_func, "test")
            mock_func.assert_called_once_with("test")


async def test_websocket_utils(test_charger):
    """Test websocket utility methods."""
    # Test ws_state when websocket is None
    assert test_charger.ws_state == STATE_STOPPED
    # Test ws_disconnect when websocket is None
    await test_charger.ws_disconnect()
    assert test_charger._ws_listening is False

    # Test with mock websocket
    mock_ws = MagicMock()
    mock_ws.close = AsyncMock()
    mock_ws.state = "connected"
    test_charger.websocket = mock_ws
    assert test_charger.ws_state == "connected"
    await test_charger.ws_disconnect()
    mock_ws.close.assert_called_once()
    assert test_charger._ws_listening is False


async def test_is_coroutine_function(test_charger):
    """Test is_coroutine_function utility."""

    async def async_func():
        pass

    def sync_func():
        pass

    assert test_charger.is_coroutine_function(async_func) is True
    assert test_charger.is_coroutine_function(sync_func) is False


# ── get_schedule ─────────────────────────────────────────────────────


async def test_get_schedule(mock_aioclient):
    """Test get_schedule method."""
    mock_aioclient.post(
        "http://openevse.test.tld/schedule",
        status=200,
        body='{"sc": 1}',
    )
    charger = OpenEVSE(SERVER_URL)
    result = await charger.get_schedule()
    assert result == {"sc": 1}


# ── auth instantiation ──────────────────────────────────────────────


async def test_main_auth_instantiation():
    """Test OpenEVSE auth instantiation."""
    charger = OpenEVSE(SERVER_URL, user="user", pwd=DUMMY_PWD)

    # Setup mock session to be an async context manager
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Setup mock response context to be an async context manager
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text.return_value = "{}"

    mock_request_ctx = MagicMock()
    mock_request_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_request_ctx.__aexit__ = AsyncMock(return_value=None)

    # Ensure session.get() returns the request context
    mock_session.get.return_value = mock_request_ctx

    with (
        patch("aiohttp.ClientSession", return_value=mock_session),
        patch("aiohttp.BasicAuth") as mock_basic_auth,
    ):
        await charger.update()

        # Verify BasicAuth was instantiated
        # Note: process_request is called multiple times in update(), so we check if called at least once
        mock_basic_auth.assert_called_with("user", DUMMY_PWD)


async def test_main_sync_callback():
    """Test synchronous callback in _update_status."""
    charger = OpenEVSE(SERVER_URL)
    sync_callback = MagicMock()
    charger.callback = sync_callback

    # Manually trigger update status
    await charger._update_status("data", {"key": "value"}, None)

    sync_callback.assert_called_once()


# ── send_command fallback tests ──────────────────────────────────────


async def test_send_command_msg_fallback():
    """Test send_command return logic fallback."""
    charger = OpenEVSE(SERVER_URL)

    # Mock response with 'msg' but no 'ret'
    with patch.object(charger, "process_request", return_value={"msg": "ErrorMsg"}):
        cmd, ret = await charger.send_command("$ST")
        assert cmd is False
        assert ret == "ErrorMsg"


async def test_send_command_rapi_rejection(test_charger, mock_aioclient):
    """Test send_command with RAPI rejection patterns."""
    # Mock charger state for toggle_override
    test_charger._status["state"] = 2  # connected, not sleeping
    test_charger._config["version"] = "3.11.0"  # Force RAPI path

    # Test $NK rejection
    value = {"cmd": "$FS", "ret": "$NK^21"}
    mock_aioclient.post(TEST_URL_RAPI, status=200, body=json.dumps(value))

    with pytest.raises(
        RuntimeError, match=r"Failed to toggle override via RAPI: \$NK\^21"
    ):
        await test_charger.toggle_override()

    # Test ESP32 timeout error
    value = {"cmd": "$FS", "ret": "RAPI_RESPONSE_TIMEOUT"}
    mock_aioclient.post(TEST_URL_RAPI, status=200, body=json.dumps(value))

    with pytest.raises(
        RuntimeError, match="Failed to toggle override via RAPI: RAPI_RESPONSE_TIMEOUT"
    ):
        await test_charger.toggle_override()


async def test_send_command_empty_fallback():
    """Test send_command empty fallback."""
    charger = OpenEVSE(SERVER_URL)
    # Mock response with neither 'msg' nor 'ret'
    with patch.object(charger, "process_request", return_value={}):
        cmd, ret = await charger.send_command("$ST")
        assert cmd is False
        assert ret == ""


async def test_restart_evse_rapi_failure(test_charger, mock_aioclient, caplog):
    """Test restart_evse with RAPI failure."""
    test_charger._config["version"] = "4.0.0"
    mock_aioclient.post(
        TEST_URL_RAPI, status=200, body='{"cmd": "$FR", "ret": "$NK^21"}'
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            RuntimeError, match="Failed to restart EVSE module via RAPI:"
        ):
            await test_charger.restart_evse()
    assert "Problem restarting EVSE module via RAPI: $NK^21" in caplog.text


def test_ws_start_no_loop_with_session(caplog):
    """Test ws_start when no loop is running but a session exists."""
    charger = OpenEVSE("test.host", session=MagicMock())
    with (
        patch("asyncio.get_running_loop", side_effect=RuntimeError),
        patch.object(charger, "_start_listening"),
        caplog.at_level(logging.WARNING),
    ):
        charger.ws_start()
    assert "Caller-provided session may not work on private event loop" in caplog.text
    # charger.websocket.session should be None so it can be auto-created on the new loop
    assert charger.websocket.session is None


def test_ws_start_no_loop_no_session():
    """Test ws_start when no loop is running and no session exists."""
    charger = OpenEVSE("test.host")
    with patch("asyncio.get_running_loop", side_effect=RuntimeError):
        with patch.object(charger, "_start_listening"):
            charger.ws_start()
    assert charger.websocket is not None


# ── process_request error handling ───────────────────────────────────


async def test_process_request_missing_method():
    """Test process_request raises error when method is None."""

    charger = OpenEVSE(SERVER_URL)

    with pytest.raises(MissingMethod):
        await charger.process_request(TEST_URL_STATUS, method=None)


async def test_process_request_unicode_decode_error(mock_aioclient):
    """Test process_request handles UnicodeDecodeError."""
    # Create a mock response that raises UnicodeDecodeError on text()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(
        side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "")
    )
    mock_response.read = AsyncMock(return_value=b'{"status": "ok"}')

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body='{"status": "ok"}',
    )

    # Patch the session.get to return our mock response
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        charger = OpenEVSE(SERVER_URL)
        result = await charger.process_request(TEST_URL_STATUS, method="get")

        assert result == {"status": "ok"}


async def test_process_request_non_json_response(mock_aioclient):
    """Test process_request handles non-JSON response."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body="Not JSON",
    )

    charger = OpenEVSE(SERVER_URL)
    result = await charger.process_request(TEST_URL_STATUS, method="get")

    # Should return the string as-is
    assert result == "Not JSON"


async def test_process_request_400_error_with_msg(mock_aioclient):
    """Test process_request handles 400 error with msg field."""

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=400,
        body='{"msg": "Bad request"}',
    )

    charger = OpenEVSE(SERVER_URL)

    with pytest.raises(ParseJSONError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_400_error_with_error_field(mock_aioclient):
    """Test process_request handles 400 error with error field."""

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=400,
        body='{"error": "Invalid input"}',
    )

    charger = OpenEVSE(SERVER_URL)

    with pytest.raises(ParseJSONError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_401_error(mock_aioclient):
    """Test process_request handles 401 authentication error."""

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=401,
        body='{"error": "Unauthorized"}',
    )

    charger = OpenEVSE(SERVER_URL)

    with pytest.raises(AuthenticationError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_404_error(mock_aioclient):
    """Test process_request handles 404 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=404,
        body='{"error": "Not found"}',
    )

    charger = OpenEVSE(SERVER_URL)
    # Should not raise, just log warning
    result = await charger.process_request(TEST_URL_STATUS, method="get")
    assert result == {"error": "Not found"}


async def test_process_request_405_error(mock_aioclient):
    """Test process_request handles 405 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=405,
        body='{"error": "Method not allowed"}',
    )

    charger = OpenEVSE(SERVER_URL)
    # Should not raise, just log warning
    result = await charger.process_request(TEST_URL_STATUS, method="get")
    assert result == {"error": "Method not allowed"}


async def test_process_request_500_error(mock_aioclient):
    """Test process_request handles 500 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=500,
        body='{"error": "Internal server error"}',
    )

    charger = OpenEVSE(SERVER_URL)
    # Should not raise, just log warning
    result = await charger.process_request(TEST_URL_STATUS, method="get")
    assert result == {"error": "Internal server error"}


async def test_process_request_timeout_error():
    """Test process_request handles TimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = TimeoutError("Connection timeout")

        charger = OpenEVSE(SERVER_URL)

        with pytest.raises(TimeoutError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_server_timeout_error():
    """Test process_request handles ServerTimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = ServerTimeoutError("Server timeout")

        charger = OpenEVSE(SERVER_URL)

        with pytest.raises(ServerTimeoutError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_content_type_error():
    """Test process_request handles ContentTypeError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        error = ContentTypeError(
            request_info=MagicMock(),
            history=(),
            message="Invalid content type",
        )
        mock_get.side_effect = error

        charger = OpenEVSE(SERVER_URL)

        with pytest.raises(ContentTypeError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_invalid_method(test_charger):
    """Test process_request with invalid method."""
    with pytest.raises(MissingMethod):
        await test_charger.process_request(TEST_URL_STATUS, method="invalid")


async def test_process_request_with_session_invalid_method(test_charger):
    """Test _process_request_with_session with invalid method."""
    async with aiohttp.ClientSession() as session:
        with pytest.raises(MissingMethod):
            await test_charger._process_request_with_session(
                session, "http://test", "invalid", None, None, None
            )


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
@pytest.mark.parametrize("trigger_key", UPDATE_TRIGGERS)
async def test_process_request_triggers_update(method, trigger_key, mock_aioclient):
    """Test process_request calls update when response contains a trigger key."""
    url = f"{TEST_URL_CONFIG}/test"
    # Register the mock for the specific method
    getattr(mock_aioclient, method)(
        url,
        status=200,
        body=json.dumps({trigger_key: "1.0"}),
    )
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )

    charger = OpenEVSE(SERVER_URL)
    # Ensure _status is fresh
    charger._status = {}

    # This should trigger update() because of trigger_key in response
    result = await charger.process_request(url, method=method, data={})

    assert trigger_key in result
    # Verify update was called by checking if status was set
    assert charger._status != {}


async def test_send_command_no_ret_with_msg(mock_aioclient):
    """Test send_command when response has msg but no ret."""
    mock_aioclient.post(
        "http://openevse.test.tld/r",
        status=200,
        body='{"msg": "Command failed"}',
    )

    charger = OpenEVSE(SERVER_URL)
    result = await charger.send_command("test_command")

    assert result == (False, "Command failed")


async def test_send_command_no_ret_no_msg(mock_aioclient):
    """Test send_command when response has neither ret nor msg."""
    mock_aioclient.post(
        "http://openevse.test.tld/r",
        status=200,
        body='{"error": "Unknown"}',
    )

    charger = OpenEVSE(SERVER_URL)
    result = await charger.send_command("test_command")

    assert result == (False, "")


# ── error status ─────────────────────────────────────────────────────


async def test_get_status_error(test_charger_timeout, caplog):
    """Test status update with timeout error."""
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(TimeoutError):
            await test_charger_timeout.update()
        assert not test_charger_timeout._ws_listening
    assert "Updating data from http://openevse.test.tld/status" in caplog.text
    assert "Status update:" not in caplog.text
    assert "Config update:" not in caplog.text


async def test_update_error_payload(mock_aioclient, caplog):
    """Test update handles responses with error keys properly."""
    # Temporarily set ws_listening to False to hit both /status and /config
    charger = OpenEVSE(SERVER_URL)
    charger._ws_listening = False

    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body='{"error": "status error"}',
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"error": "config error"}',
    )
    charger._status = {"old": "status"}
    charger._config = {"old": "config"}

    with caplog.at_level(logging.WARNING):
        await charger.update()

    assert charger._status == {"old": "status"}
    assert charger._config == {"old": "config"}
    assert "Error in /status response: status error" in caplog.text
    assert "Error in /config response: config error" in caplog.text


# ── external session ─────────────────────────────────────────────────


async def test_external_session_with_error_handling(mock_aioclient):
    """Test external session handles errors properly."""

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=401,
        body='{"error": "Unauthorized"}',
    )

    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)

        with pytest.raises(AuthenticationError):
            await charger.process_request(TEST_URL_STATUS, method="get")

        # Session should still be open
        assert not session.closed


async def test_external_session_unicode_decode_error():
    """Test external session handles UnicodeDecodeError."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(
        side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "")
    )
    mock_response.read = AsyncMock(return_value=b'{"status": "ok"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == {"status": "ok"}


async def test_external_session_non_json_response():
    """Test external session handles non-JSON response."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="Not JSON")

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == "Not JSON"


async def test_external_session_400_error_with_msg():
    """Test external session handles 400 error with msg field."""
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"msg": "Bad request"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(ParseJSONError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_400_error_with_error_field():
    """Test external session handles 400 error with error field."""
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"error": "Invalid input"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(ParseJSONError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_401_error():
    """Test external session handles 401 authentication error."""
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.text = AsyncMock(return_value='{"error": "Unauthorized"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(AuthenticationError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_404_error():
    """Test external session handles 404 error."""
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value='{"error": "Not found"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == {"error": "Not found"}


async def test_external_session_405_error():
    """Test external session handles 405 error."""
    mock_response = AsyncMock()
    mock_response.status = 405
    mock_response.text = AsyncMock(return_value='{"error": "Method not allowed"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == {"error": "Method not allowed"}


async def test_external_session_500_error():
    """Test external session handles 500 error."""
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value='{"error": "Internal server error"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == {"error": "Internal server error"}


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
@pytest.mark.parametrize("trigger_key", UPDATE_TRIGGERS)
async def test_external_session_triggers_update(method, trigger_key, mock_aioclient):
    """Test external session with methods that trigger update."""
    url = f"{TEST_URL_CONFIG}/test_external"
    getattr(mock_aioclient, method)(
        url,
        status=200,
        body=json.dumps({trigger_key: "1.0"}),
    )
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )

    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)
        # Ensure _status is fresh
        charger._status = {}
        result = await charger.process_request(url, method=method, data={})

        assert trigger_key in result
        assert charger._status != {}


async def test_external_session_timeout_error():
    """Test external session handles TimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = TimeoutError("Connection timeout")

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(TimeoutError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_server_timeout_error():
    """Test external session handles ServerTimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = ServerTimeoutError("Server timeout")

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(ServerTimeoutError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_content_type_error():
    """Test external session handles ContentTypeError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        error = ContentTypeError(
            request_info=MagicMock(),
            history=(),
            message="Invalid content type",
        )
        mock_get.side_effect = error

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(ContentTypeError):
                await charger.process_request(TEST_URL_STATUS, method="get")


# ── websocket pong / listen / stop ───────────────────────────────────


async def test_websocket_pong():
    """Test websocket handles pong message."""

    callback = AsyncMock()
    async with aiohttp.ClientSession() as session:
        ws = OpenEVSEWebsocket(f"http://{SERVER_URL}", callback, session=session)

        mock_ws = AsyncMock()
        # Mock the async iterator of ws_client
        msg1 = MagicMock()
        msg1.type = aiohttp.WSMsgType.TEXT
        msg1.json.return_value = {"pong": 1}
        msg2 = MagicMock()
        msg2.type = aiohttp.WSMsgType.TEXT
        msg2.json.return_value = {"data": 1}
        mock_ws.__aiter__.return_value = [msg1, msg2]

        with patch.object(session, "ws_connect") as mock_ws_connect:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_ws
            mock_ws_connect.return_value = mock_context

            # Set state to stopped after one iteration to break the loop
            ws.state = "connected"

            async def side_effect(msgtype, data, error):
                if msgtype == SIGNAL_CONNECTION_STATE and data == STATE_STOPPED:
                    pass
                elif msgtype == "data" and "data" in data:
                    ws.state = "stopped"

            callback.side_effect = side_effect

            await ws.running()
            assert ws._pong is not None


async def test_websocket_listen():
    """Test websocket listen calls running."""

    callback = AsyncMock()
    ws = OpenEVSEWebsocket(f"http://{SERVER_URL}", callback)

    with patch.object(ws, "running", AsyncMock()) as mock_running:
        # Break loop after first call
        ws.state = "starting"

        async def side_effect():
            ws.state = "stopped"

        mock_running.side_effect = side_effect

        try:
            await ws.listen()
        finally:
            await ws.close()
        mock_running.assert_called_once()


async def test_websocket_stop_break():
    """Test websocket stops loop when state is stopped."""

    callback = AsyncMock()
    async with aiohttp.ClientSession() as session:
        ws = OpenEVSEWebsocket(f"http://{SERVER_URL}", callback, session=session)

        mock_ws = AsyncMock()
        msg = MagicMock()
        msg.type = aiohttp.WSMsgType.TEXT
        msg.json.return_value = {"test": 1}
        mock_ws.__aiter__.return_value = [msg, msg]

        with patch.object(session, "ws_connect") as mock_ws_connect:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_ws
            mock_ws_connect.return_value = mock_context

            ws.state = "connected"

            async def side_effect(msgtype, _data, _error):
                if msgtype == "data":
                    ws._state = "stopped"  # Direct set to avoid callback loop

            callback.side_effect = side_effect

            await ws.running()
            # Check that we received "data" once
            calls = [call for call in callback.call_args_list if call[0][0] == "data"]
            assert len(calls) == 1


async def test_repeat_task():
    """Test the repeat background task."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.state = "connected"

    mock_func = MagicMock(return_value=asyncio.Future())
    mock_func.return_value.set_result(None)

    # Launch repeat task with very short interval
    task = asyncio.create_task(charger.repeat(0.001, mock_func))

    # Wait for execution and ensure loop body is hit
    for _ in range(10):
        if mock_func.called:
            break
        await asyncio.sleep(0.01)

    assert mock_func.called

    # Stop and wait for termination
    charger.websocket.state = STATE_STOPPED
    # Give it one more micro-sleep to exit the loop
    await asyncio.sleep(0.01)
    await task
    assert task.done()


async def test_ws_disconnect_owned_loop():
    """Test ws_disconnect when the client owns the event loop."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.state = STATE_STOPPED

    # Mock loop finding to fail
    with patch("asyncio.get_running_loop", side_effect=RuntimeError):
        # Mock loop methods to avoid real async operations
        mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
        with patch("asyncio.new_event_loop", return_value=mock_loop):
            with patch("threading.Thread"):
                with (
                    patch.object(charger, "repeat", return_value=None),
                    patch.object(charger.websocket, "listen", return_value=None),
                ):
                    charger._start_listening()
                    assert charger._owns_loop is True
                    assert charger._loop is mock_loop

                # Mock thread
                mock_thread = MagicMock()
                mock_thread.is_alive.return_value = False
                charger._loop_thread = mock_thread

                # Mock run_coroutine_threadsafe to return a success future
                from concurrent.futures import Future as ConcurrentFuture

                mock_future = ConcurrentFuture()
                mock_future.set_result(True)
                with (
                    patch(
                        "asyncio.run_coroutine_threadsafe", return_value=mock_future
                    ) as mock_run,
                    patch("asyncio.wait_for", AsyncMock(return_value=True)),
                    patch(
                        "asyncio.to_thread",
                        AsyncMock(side_effect=lambda func, *args: func(*args)),
                    ),
                    patch.object(charger, "_shutdown", AsyncMock()) as mock_shutdown,
                ):
                    await charger.ws_disconnect()
                    # Check for threadsafe call
                    assert mock_run.called
                    assert mock_shutdown.called

                assert charger._loop is None
                assert mock_loop.close.called


async def test_ws_disconnect_exception():
    """Test ws_disconnect handled exceptions during shutdown."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.state = STATE_STOPPED

    # Mock loop methods to avoid real async operations
    mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
    charger._loop = mock_loop
    charger._owns_loop = True

    # Mock thread
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = False
    charger._loop_thread = mock_thread

    # Mock run_coroutine_threadsafe to return a failing future
    from concurrent.futures import Future as ConcurrentFuture

    mock_future = ConcurrentFuture()
    mock_future.set_exception(asyncio.TimeoutError)
    with (
        patch("asyncio.run_coroutine_threadsafe", return_value=mock_future) as mock_run,
        patch("asyncio.wait_for", AsyncMock(side_effect=asyncio.TimeoutError)),
        patch(
            "asyncio.to_thread", AsyncMock(side_effect=lambda func, *args: func(*args))
        ),
        patch.object(charger, "_shutdown", AsyncMock()) as mock_shutdown,
    ):
        await charger.ws_disconnect()
        assert mock_run.called
        assert mock_shutdown.called

    # Shutdown failed, so loop should NOT be closed/cleared
    assert charger._loop is mock_loop


async def test_ws_shutdown_drains_tasks(test_charger):
    """Test that _shutdown cancels pending tasks."""
    mock_task = asyncio.Future()
    ws_mock = MagicMock()
    ws_mock._tasks = {mock_task}
    ws_mock.close = AsyncMock()
    test_charger.websocket = ws_mock
    test_charger._owns_loop = True
    test_charger._loop = MagicMock()

    await test_charger._shutdown()

    assert mock_task.cancelled()
    assert len(ws_mock._tasks) == 0
    assert test_charger.websocket is None


async def test_test_and_get_invalid_response(mock_aioclient, caplog):
    """Test test_and_get method with invalid response."""
    mock_aioclient.get(TEST_URL_CONFIG, status=200, body="not a dict")
    charger = OpenEVSE(SERVER_URL)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(MissingSerial):
            await charger.test_and_get()
    assert "Invalid response from config: not a dict" in caplog.text


async def test_update_status_non_mapping_data(caplog):
    """Test _update_status with non-mapping data."""
    charger = OpenEVSE(SERVER_URL)
    with caplog.at_level(logging.WARNING):
        await charger._update_status("data", "not a dict", None)
    assert "Received non-Mapping websocket data: not a dict" in caplog.text
