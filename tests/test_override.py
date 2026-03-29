"""Tests for Override module."""

import json
import logging
from unittest import mock

import pytest
from aiohttp.client_exceptions import ContentTypeError

from openevsehttp.exceptions import UnsupportedFeature
from tests.const import TEST_URL_OVERRIDE, TEST_URL_RAPI

pytestmark = pytest.mark.asyncio


async def test_toggle_override(
    test_charger,
    test_charger_dev,
    test_charger_new,
    test_charger_modified_ver,
    mock_aioclient,
    caplog,
):
    """Test v4 Status reply."""
    await test_charger.update()
    mock_aioclient.patch(
        TEST_URL_OVERRIDE,
        status=200,
        body="OK",
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.toggle_override()
    assert "Toggling manual override http" in caplog.text
    await test_charger.ws_disconnect()

    await test_charger_dev.update()
    with caplog.at_level(logging.DEBUG):
        await test_charger_dev.toggle_override()
    assert "Stripping 'dev' from version." in caplog.text
    assert "Toggling manual override http" in caplog.text
    await test_charger_dev.ws_disconnect()

    value = {
        "state": "active",
        "charge_current": 0,
        "max_current": 0,
        "energy_limit": 0,
        "time_limit": 0,
        "auto_release": True,
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )

    await test_charger_new.update()
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.toggle_override()
    assert "Toggling manual override http" in caplog.text
    await test_charger_new.ws_disconnect()

    value = {
        "state": "disabled",
        "charge_current": 0,
        "max_current": 0,
        "energy_limit": 0,
        "time_limit": 0,
        "auto_release": True,
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )

    with caplog.at_level(logging.DEBUG):
        await test_charger_new.toggle_override()
    assert "Toggling manual override http" in caplog.text

    await test_charger_modified_ver.update()

    value = {
        "state": "disabled",
        "charge_current": 0,
        "max_current": 0,
        "energy_limit": 0,
        "time_limit": 0,
        "auto_release": True,
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )

    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.toggle_override()
        assert "Detected firmware: v5.0.1_modified" in caplog.text
        assert "Filtered firmware: 5.0.1" in caplog.text
    await test_charger_modified_ver.ws_disconnect()


async def test_toggle_override_v2(test_charger_v2, mock_aioclient, caplog):
    """Test v4 Status reply."""
    await test_charger_v2.update()
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_v2.toggle_override()
    assert "Toggling manual override via RAPI" in caplog.text


async def test_toggle_override_v2_err(test_charger_v2, mock_aioclient, caplog):
    """Test v4 Status reply."""
    await test_charger_v2.update()
    content_error = mock.Mock()
    content_error.real_url = f"{TEST_URL_RAPI}"
    mock_aioclient.post(
        TEST_URL_RAPI,
        exception=ContentTypeError(
            content_error,
            history="",
            message="Attempt to decode JSON with unexpected mimetype: text/html",
        ),
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ContentTypeError):
            await test_charger_v2.toggle_override()
    assert (
        "Content error: Attempt to decode JSON with unexpected mimetype: text/html"
        in caplog.text
    )


async def test_set_override(
    test_charger, test_charger_v2, test_charger_unknown_semver, mock_aioclient, caplog
):
    """Test set override function."""
    await test_charger.update()
    value = {
        "state": "active",
        "charge_current": 0,
        "max_current": 0,
        "energy_limit": 0,
        "time_limit": 0,
        "auto_release": True,
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        status = await test_charger.set_override("active")
        assert status == {"msg": "OK"}
        assert (
            "Override data: {'state': 'active', 'charge_current': 0, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )

        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override("active", 30)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )
        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override(charge_current=30)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )
        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override("active", 30, 32)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )
        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override("active", 30, 32, 2000)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 2000, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )
        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override("active", 30, 32, 2000, 5000)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 2000, 'time_limit': 5000, 'auto_release': True}"
            in caplog.text
        )

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError):
            await test_charger.set_override("invalid")
    assert "Invalid override state: invalid" in caplog.text

    await test_charger_v2.update()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_v2.set_override("active")
    assert "Feature not supported for older firmware." in caplog.text

    await test_charger_unknown_semver.update()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_unknown_semver.set_override("active")
    assert "Feature not supported for older firmware." in caplog.text


async def test_clear_override(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test clear override function."""
    await test_charger.update()
    mock_aioclient.delete(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.clear_override()
        assert "Toggle response: OK" in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.update()
            await test_charger_v2.clear_override()
            assert "Feature not supported for older firmware." in caplog.text


async def test_get_override(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test get override function."""
    await test_charger.update()
    value = {
        "state": "active",
        "charge_current": 0,
        "max_current": 0,
        "energy_limit": 0,
        "time_limit": 0,
        "auto_release": True,
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        status = await test_charger.get_override()
        assert status == value

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.update()
            await test_charger_v2.get_override()
            assert "Feature not supported for older firmware." in caplog.text


async def test_set_override_partial(test_charger, mock_aioclient, caplog):
    """Test partial override updates."""
    await test_charger.update()
    value = {
        "state": "active",
        "charge_current": 32,
        "max_current": 32,
        "energy_limit": 1000,
        "time_limit": 3600,
        "auto_release": False,
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        # Only change state, auto_release should remain False
        await test_charger.set_override(state="disabled")
        assert "'state': 'disabled'" in caplog.text
        assert "'auto_release': False" in caplog.text

    with caplog.at_level(logging.DEBUG):
        # Change auto_release to True
        await test_charger.set_override(auto_release=True)
        assert "'auto_release': True" in caplog.text


async def test_clear_override_non_dict(test_charger, mock_aioclient, caplog):
    """Test clear override with non-dict response."""
    await test_charger.update()
    mock_aioclient.delete(
        TEST_URL_OVERRIDE,
        status=200,
        body="Clear successful",
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.clear_override()
        assert "Toggle response: Clear successful" in caplog.text
