"""Edge case tests for OpenEVSE main library."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

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

    with patch("aiohttp.ClientSession.get", return_value=mock_resp), caplog.at_level(
        logging.DEBUG
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

    with patch("aiohttp.ClientSession.get", return_value=mock_resp), caplog.at_level(
        logging.WARNING
    ):
        await charger.process_request("http://url", method="get")
        # Verify the 404 response body was logged as a warning
        assert "{'msg': 'Not Found'}" in caplog.text
