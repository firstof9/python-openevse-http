"""Edge case tests for OpenEVSE main library."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from openevsehttp.__main__ import OpenEVSE

pytestmark = pytest.mark.asyncio

SERVER_URL = "openevse.test.tld"


@pytest.fixture
def charger():
    return OpenEVSE(SERVER_URL)


async def test_process_request_decode_error(charger, caplog):
    """Test handling of UnicodeDecodeError in process_request."""
    mock_resp = MagicMock()

    # .text() needs to be an async mock that raises the error
    mock_resp.text = AsyncMock(
        side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "err")
    )

    # .read() needs to be an async mock that returns the bytes
    mock_resp.read = AsyncMock(return_value=b'{"msg": "decoded"}')

    mock_resp.status = 200
    mock_resp.__aenter__.return_value = mock_resp
    mock_resp.__aexit__.return_value = None

    with (
        patch("aiohttp.ClientSession.get", return_value=mock_resp),
        caplog.at_level(logging.DEBUG),
    ):
        data = await charger.process_request("http://url", method="get")

        assert data == {"msg": "decoded"}
        assert "Decoding error" in caplog.text


async def test_process_request_http_warnings(charger, caplog):
    """Test logging of specific HTTP error codes."""
    mock_resp = MagicMock()

    # .text() needs to be an async mock that returns the string
    mock_resp.text = AsyncMock(return_value='{"msg": "Not Found"}')

    mock_resp.status = 404
    mock_resp.__aenter__.return_value = mock_resp
    mock_resp.__aexit__.return_value = None

    with (
        patch("aiohttp.ClientSession.get", return_value=mock_resp),
        caplog.at_level(logging.WARNING),
    ):
        await charger.process_request("http://url", method="get")
        # Verify the 404 response body was logged as a warning
        assert "{'msg': 'Not Found'}" in caplog.text


async def test_session_property_creates_session_lazily(charger):
    """Test that session property creates an aiohttp.ClientSession when none provided."""
    assert charger._session is None
    session = charger.session
    assert session is not None
    assert isinstance(session, aiohttp.ClientSession)
    # Second access should return the same session
    assert charger.session is session
    await session.close()


async def test_session_property_returns_provided_session():
    """Test that session property returns a pre-provided session."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    charger = OpenEVSE(SERVER_URL, session=mock_session)
    assert charger._session is mock_session
    assert charger.session is mock_session


async def test_init_with_custom_session():
    """Test OpenEVSE constructor stores the provided session."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    charger = OpenEVSE(SERVER_URL, session=mock_session)
    assert charger._session is mock_session
    assert charger.url == f"http://{SERVER_URL}/"


async def test_update_passes_session_to_websocket(mock_aioclient):
    """Test that update() passes the session to OpenEVSEWebsocket."""
    from tests.common import load_fixture

    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body=load_fixture("v4_json/config.json"),
    )

    charger = OpenEVSE(SERVER_URL)

    with patch("openevsehttp.__main__.OpenEVSEWebsocket") as mock_ws_cls:
        await charger.update()
        mock_ws_cls.assert_called_once_with(
            charger.url,
            charger._update_status,
            charger._user,
            charger._pwd,
            session=charger.session,
        )
    await charger.session.close()
