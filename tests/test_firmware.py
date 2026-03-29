"""Tests for Firmware module."""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from awesomeversion.exceptions import AwesomeVersionCompareException

from openevsehttp.__main__ import OpenEVSE
from tests.common import load_fixture
from tests.const import (
    SERVER_URL,
    TEST_URL_CONFIG,
    TEST_URL_STATUS,
    TEST_URL_GITHUB_v2,
    TEST_URL_GITHUB_v4,
)

pytestmark = pytest.mark.asyncio


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
    """Test v4 Status reply."""
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
            aiohttp.client_reqrep.ConnectionKey(
                "localhost", 80, False, None, None, None, None
            ),
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


async def test_version_check(test_charger_new, mock_aioclient, caplog):
    """Test version check function."""
    await test_charger_new.update()

    result = test_charger_new._version_check("4.0.0")
    assert result

    result = test_charger_new._version_check("4.0.0", "4.1.7")
    assert not result

    # Test version_check with dev version
    test_charger_new._config["version"] = "4.2.0.dev"
    with caplog.at_level(logging.DEBUG):
        assert test_charger_new.version_check("4.0.0") is True
    assert "Stripping 'dev' from version." in caplog.text

    # Test version_check with missing version
    test_charger_new._config = {}
    with caplog.at_level(logging.DEBUG):
        assert test_charger_new.version_check("4.0.0") is False
    assert "Unable to find firmware version." in caplog.text


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


async def test_version_check_exceptions():
    """Test _version_check exception paths."""
    charger = OpenEVSE(SERVER_URL)

    # Trigger re.search Exception
    charger._config = {"version": "invalid"}
    with patch("re.search", side_effect=Exception):
        assert charger._version_check("2.0.0") is False

    # Trigger AwesomeVersionCompareException in limit comparison
    with patch(
        "awesomeversion.AwesomeVersion.__le__",
        side_effect=AwesomeVersionCompareException,
    ):
        charger._config = {"version": "2.9.1"}
        assert charger._version_check("2.0.0", "3.0.0") is False


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
        repeat=True,
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"hostname": "test", "version": "4.0.1"}',
        repeat=True,
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
    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)
        await charger.update()
        charger._config["version"] = "4.0.1"
        assert await charger.firmware_check() is None

    # ContentTypeError from github
    request_info = MagicMock()
    request_info.real_url = "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest"
    mock_aioclient.get(url, exception=aiohttp.ContentTypeError(request_info, (), message="content type error"))
    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)
        await charger.update()
        charger._config["version"] = "4.0.1"
        assert await charger.firmware_check() is None

    # JSONDecodeError from github
    mock_aioclient.get(url, status=200, body="invalid json")
    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)
        await charger.update()
        charger._config["version"] = "4.0.1"
        assert await charger.firmware_check() is None
