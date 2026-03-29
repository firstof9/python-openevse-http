"""Tests for Requester module."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from aioresponses import aioresponses

import openevsehttp.__main__ as main
from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import AuthenticationError, MissingMethod, ParseJSONError
from tests.common import load_fixture
from tests.const import SERVER_URL, TEST_URL_CONFIG, TEST_URL_RAPI, TEST_URL_STATUS

pytestmark = pytest.mark.asyncio


async def test_get_status_auth(test_charger_auth):
    """Test v4 Status reply."""
    await test_charger_auth.update()
    status = test_charger_auth.status
    assert status == "sleeping"
    await test_charger_auth.ws_disconnect()


async def test_get_status_auth_err(test_charger_auth_err):
    """Test v4 Status reply."""
    with pytest.raises(main.AuthenticationError):
        await test_charger_auth_err.update()
        assert test_charger_auth_err is None


async def test_send_command(test_charger, mock_aioclient):
    """Test v4 Status reply."""
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == ("OK", "$OK^20")


async def test_send_command_failed(test_charger, mock_aioclient):
    """Test v4 Status reply."""
    value = {"cmd": "OK", "ret": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == ("OK", "$NK^21")


async def test_send_command_missing(test_charger, mock_aioclient):
    """Test v4 Status reply."""
    value = {"cmd": "OK", "what": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == (False, "")


async def test_send_command_auth(test_charger_auth, mock_aioclient):
    """Test v4 Status reply."""
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger_auth.send_command("test")
    assert status == ("OK", "$OK^20")


async def test_send_command_parse_err(test_charger_auth, mock_aioclient):
    """Test v4 Status reply."""
    mock_aioclient.post(
        TEST_URL_RAPI, status=400, body='{"msg": "Could not parse JSON"}'
    )
    with pytest.raises(main.ParseJSONError):
        status = await test_charger_auth.send_command("test")
        assert status is None

    mock_aioclient.post(
        TEST_URL_RAPI, status=400, body='{"error": "Could not parse JSON"}'
    )
    with pytest.raises(main.ParseJSONError):
        status = await test_charger_auth.send_command("test")
        assert status is None

    mock_aioclient.post(TEST_URL_RAPI, status=400, body='{"other": "Something else"}')
    with pytest.raises(main.ParseJSONError):
        status = await test_charger_auth.send_command("test")
        assert status is None

    mock_aioclient.post(TEST_URL_RAPI, status=400, body='"Just a string response"')
    with pytest.raises(main.ParseJSONError):
        status = await test_charger_auth.send_command("test")
        assert status is None


async def test_non_json_response():
    """Test non-JSON response is wrapped in dict."""
    with aioresponses() as m:
        m.get(
            f"http://{SERVER_URL}/status",
            status=200,
            body="Plain text message",
        )
        m.get(
            f"http://{SERVER_URL}/config",
            status=200,
            body='{"firmware": "5.0.0"}',
        )
        c = OpenEVSE(SERVER_URL)
        await c.update()
        assert c._status == {"msg": "Plain text message"}


async def test_send_command_auth_err(test_charger_auth, mock_aioclient):
    """Test v4 Status reply."""
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=401,
    )
    with pytest.raises(main.AuthenticationError):
        status = await test_charger_auth.send_command("test")
        assert status is None


async def test_send_command_async_timeout(test_charger_auth, mock_aioclient, caplog):
    """Test v4 Status reply."""
    mock_aioclient.post(
        TEST_URL_RAPI,
        exception=asyncio.TimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(asyncio.TimeoutError):
            await test_charger_auth.send_command("test")
    assert main.ERROR_TIMEOUT in caplog.text


async def test_send_command_server_timeout(test_charger_auth, mock_aioclient, caplog):
    """Test v4 Status reply."""
    mock_aioclient.post(
        TEST_URL_RAPI,
        exception=ServerTimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(main.ServerTimeoutError):
            await test_charger_auth.send_command("test")
    assert f"{main.ERROR_TIMEOUT}: {TEST_URL_RAPI}" in caplog.text


async def test_send_command_no_ret_with_msg(mock_aioclient):
    """Test send_command with no 'ret' but 'msg' in response."""
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"msg": "ErrorMsg"}',
    )
    charger = OpenEVSE(SERVER_URL)
    cmd, ret = await charger.send_command("$ST")
    assert cmd is False
    assert ret == "ErrorMsg"


async def test_send_command_no_ret_no_msg(mock_aioclient):
    """Test send_command with neither 'ret' nor 'msg' in response."""
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body="{}",
    )
    charger = OpenEVSE(SERVER_URL)
    cmd, ret = await charger.send_command("$ST")
    assert cmd is False
    assert ret == ""


async def test_send_command_empty_fallback():
    """Test send_command empty fallback."""
    charger = OpenEVSE(SERVER_URL)

    # Mock response with neither 'msg' nor 'ret'
    with patch.object(charger.requester, "process_request", return_value={}):
        cmd, ret = await charger.send_command("$ST")
        assert cmd is False
        assert ret == ""


async def test_process_request_missing_method_raise():
    """Test process_request with method=None raises MissingMethod."""
    charger = OpenEVSE(SERVER_URL)
    from openevsehttp.exceptions import MissingMethod

    with pytest.raises(MissingMethod):
        await charger.process_request(TEST_URL_STATUS, method=None)


async def test_process_request_missing_method():
    """Test process_request with missing method."""
    charger = OpenEVSE(SERVER_URL)
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = AsyncMock(
            status=200, text=AsyncMock(return_value="{}")
        )
        await charger.process_request(TEST_URL_STATUS)
        mock_get.assert_called_once()


async def test_process_request_unicode_decode_error(mock_aioclient):
    """Test process_request handles UnicodeDecodeError."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=b'{"status": "ok"}',
    )
    with patch(
        "aiohttp.ClientResponse.text",
        side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, ""),
    ):
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
    assert result == {"msg": "Not JSON"}


async def test_process_request_400_error_with_msg(mock_aioclient):
    """Test process_request handles 400 error with msg."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=400,
        body='{"msg": "Error"}',
    )
    charger = OpenEVSE(SERVER_URL)
    with pytest.raises(ParseJSONError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_400_error_with_error_field(mock_aioclient):
    """Test process_request handles 400 error with error field."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=400,
        body='{"error": "Error"}',
    )
    charger = OpenEVSE(SERVER_URL)
    with pytest.raises(ParseJSONError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_401_error(mock_aioclient):
    """Test process_request handles 401 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=401,
    )
    charger = OpenEVSE(SERVER_URL)
    with pytest.raises(AuthenticationError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_404_error(mock_aioclient, caplog):
    """Test process_request handles 404 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=404,
        body='{"error": "Not found"}',
    )
    charger = OpenEVSE(SERVER_URL)
    with caplog.at_level(logging.WARNING):
        result = await charger.process_request(TEST_URL_STATUS, method="get")
        assert result == {"error": "Not found", "ok": False, "status": 404}
        assert "{'error': 'Not found'}" in caplog.text


async def test_process_request_405_error(mock_aioclient):
    """Test process_request handles 405 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=405,
        body="Method not allowed",
    )
    charger = OpenEVSE(SERVER_URL)
    result = await charger.process_request(TEST_URL_STATUS, method="get")
    assert result == {"msg": "Method not allowed", "ok": False, "status": 405}


async def test_process_request_500_error(mock_aioclient):
    """Test process_request handles 500 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=500,
        body="[]",
    )
    charger = OpenEVSE(SERVER_URL)
    result = await charger.process_request(TEST_URL_STATUS, method="get")
    assert result == {"msg": [], "ok": False, "status": 500}


async def test_process_request_timeout_error():
    """Test process_request handles TimeoutError."""
    with patch("aiohttp.ClientSession.get", side_effect=asyncio.TimeoutError):
        charger = OpenEVSE(SERVER_URL)
        with pytest.raises(asyncio.TimeoutError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_server_timeout_error():
    """Test process_request handles ServerTimeoutError."""
    with patch("aiohttp.ClientSession.get", side_effect=ServerTimeoutError):
        charger = OpenEVSE(SERVER_URL)
        with pytest.raises(ServerTimeoutError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_content_type_error():
    """Test process_request handles ContentTypeError."""
    with patch("aiohttp.ClientSession.get", side_effect=ContentTypeError(None, None)):
        charger = OpenEVSE(SERVER_URL)
        with pytest.raises(ContentTypeError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_post_with_config_version(mock_aioclient):
    """Test process_request post with config version update."""
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"config_version": 2}',
    )
    mock_aioclient.get(TEST_URL_STATUS, status=200, body="{}")
    mock_aioclient.get(TEST_URL_CONFIG, status=200, body="{}")

    charger = OpenEVSE(SERVER_URL)
    await charger.process_request(TEST_URL_CONFIG, method="post")


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

            assert result == {"msg": "Not JSON"}


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

            assert result == {"error": "Not found", "ok": False, "status": 404}


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

            assert result == {"error": "Method not allowed", "ok": False, "status": 405}


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

            assert result == {
                "error": "Internal server error",
                "ok": False,
                "status": 500,
            }


async def test_external_session_post_with_config_version(mock_aioclient):
    """Test external session with POST that triggers update."""
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"config_version": "1.0"}',
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
        result = await charger.process_request(TEST_URL_CONFIG, method="post", data={})

        assert "config_version" in result
        assert charger._status is not None


async def test_external_session_timeout_error():
    """Test external session handles TimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = asyncio.TimeoutError("Connection timeout")

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(asyncio.TimeoutError):
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


async def test_process_request_invalid_methods(mock_aioclient):
    """Test process_request with invalid and uppercase methods."""
    charger = OpenEVSE(SERVER_URL)
    with pytest.raises(MissingMethod):
        await charger.process_request(TEST_URL_STATUS, method="INVALID")

    with pytest.raises(MissingMethod):
        # Test non-string method
        await charger.process_request(TEST_URL_STATUS, method=123)

    # Upper case should be normalized and succeed
    mock_aioclient.get(TEST_URL_STATUS, status=200, body='{"msg": "done"}')
    await charger.process_request(TEST_URL_STATUS, method="GET")


async def test_process_request_post_no_callback(mock_aioclient):
    """Test POST with config_version and no callback."""
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"config_version": 1}',
    )
    from openevsehttp.requester import Requester

    req = Requester(SERVER_URL)
    # req._update_callback is None by default
    await req.process_request(TEST_URL_CONFIG, method="post", data={})
    # Should not crash on line 125/127
