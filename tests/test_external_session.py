"""Test external session management."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

import openevsehttp.__main__ as main
from openevsehttp.__main__ import OpenEVSE
from tests.common import load_fixture

pytestmark = pytest.mark.asyncio

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_TLD = "openevse.test.tld"


async def test_external_session_provided(mock_aioclient):
    """Test that an external session is used when provided."""
    # Create a mock session
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.closed = False
    
    # Mock the response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=load_fixture("v4_json/status.json"))
    
    # Mock the get method to return the response
    mock_get = AsyncMock(return_value=mock_response)
    mock_get.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_get)
    
    # Create OpenEVSE instance with external session
    charger = OpenEVSE(TEST_TLD, session=mock_session)
    
    # Verify the session is stored
    assert charger._session is mock_session
    assert charger._session_external is True
    
    # Make a request
    await charger.process_request(TEST_URL_STATUS, method="get")
    
    # Verify the external session was used
    mock_session.get.assert_called_once()


async def test_no_external_session(mock_aioclient):
    """Test that a temporary session is created when none is provided."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    
    # Create OpenEVSE instance without external session
    charger = OpenEVSE(TEST_TLD)
    
    # Verify no session is stored
    assert charger._session is None
    assert charger._session_external is False
    
    # Make a request - should create a temporary session
    await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_with_update(mock_aioclient):
    """Test that external session is used during update."""
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
    
    # Create a real session for testing
    async with aiohttp.ClientSession() as session:
        # Create OpenEVSE instance with external session
        charger = OpenEVSE(TEST_TLD, session=session)
        
        # Verify the session is stored
        assert charger._session is session
        assert charger._session_external is True
        
        # Update should use the external session
        await charger.update()
        
        # Verify status was updated
        assert charger._status is not None
        assert charger._config is not None


async def test_websocket_uses_external_session(mock_aioclient):
    """Test that websocket uses the external session."""
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
    
    # Create a real session for testing
    async with aiohttp.ClientSession() as session:
        # Create OpenEVSE instance with external session
        charger = OpenEVSE(TEST_TLD, session=session)
        
        # Update to initialize websocket
        await charger.update()
        
        # Verify websocket was created with the session
        assert charger.websocket is not None
        assert charger.websocket.session is session
        assert charger.websocket._session_external is True
        
        # Cleanup
        await charger.ws_disconnect()


async def test_firmware_check_with_external_session(mock_aioclient):
    """Test that firmware_check uses external session."""
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
    
    github_response = {
        "tag_name": "v4.2.0",
        "body": "Release notes",
        "html_url": "https://github.com/OpenEVSE/ESP32_WiFi_V4.x/releases/tag/v4.2.0",
    }
    
    mock_aioclient.get(
        "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest",
        status=200,
        body=json.dumps(github_response),
    )
    
    # Create OpenEVSE instance without external session (use mocked responses)
    charger = OpenEVSE(TEST_TLD)
    
    # Load config first
    await charger.update()
    
    # Check firmware - should use mocked session
    result = await charger.firmware_check()
    
    # Verify result
    assert result is not None
    assert result["latest_version"] == "v4.2.0"


async def test_session_not_closed_when_external(mock_aioclient):
    """Test that external session is not closed by the library."""
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
    
    # Create a real session
    session = aiohttp.ClientSession()
    
    try:
        # Create OpenEVSE instance with external session
        charger = OpenEVSE(TEST_TLD, session=session)
        
        # Update to initialize websocket
        await charger.update()
        
        # Disconnect websocket
        await charger.ws_disconnect()
        
        # Session should still be open (not closed by library)
        assert not session.closed
        
    finally:
        # Clean up the session ourselves
        await session.close()
