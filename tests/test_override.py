"""Tests for Override module."""

import json
import logging
from unittest import mock

import pytest
from aiohttp.client_exceptions import ContentTypeError

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import UnknownError, UnsupportedFeature
from tests.const import SERVER_URL, TEST_URL_OVERRIDE, TEST_URL_RAPI

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
    caplog.clear()
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
    caplog.clear()
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

    caplog.clear()
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

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.toggle_override()
        assert "Detected firmware: v5.0.1_modified" in caplog.text
        assert "Filtered firmware: 5.0.1" in caplog.text
    await test_charger_modified_ver.ws_disconnect()


async def test_toggle_override_v2(test_charger_legacy, mock_aioclient, caplog):
    """Test v4 Status reply."""
    await test_charger_legacy.update()
    value = {"cmd": "OK", "ret": "$OK"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_legacy.toggle_override()
    assert "Toggling manual override via RAPI" in caplog.text


async def test_toggle_override_v2_err(test_charger_legacy, mock_aioclient, caplog):
    """Test v4 Status reply."""
    await test_charger_legacy.update()
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
            await test_charger_legacy.toggle_override()
    assert (
        "Content error: Attempt to decode JSON with unexpected mimetype: text/html"
        in caplog.text
    )


async def test_toggle_override_v2_fail(test_charger_legacy, mock_aioclient, caplog):
    """Test v4 toggle fail."""
    await test_charger_legacy.update()
    # Mock send_command returning success=False
    # Requester returns (False, msg) if 'ret' is missing but 'msg' is present
    value = {"msg": "toggle failed"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnknownError):
            await test_charger_legacy.toggle_override()
    assert "Problem issuing command $FS. Response: toggle failed" in caplog.text


async def test_toggle_override_v2_transport_fail(
    test_charger_legacy, mock_aioclient, caplog
):
    """Test v4 toggle transport fail (returns dict)."""
    await test_charger_legacy.update()
    # Mock transport fail: ok=False in dict
    value = {"ok": False, "msg": "transport fail"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await test_charger_legacy.toggle_override()
    assert (
        "Problem toggling override ($FS): {'ok': False, 'msg': 'transport fail'}"
        in caplog.text
    )


async def test_toggle_override_empty_status(
    test_charger_legacy, mock_aioclient, caplog
):
    """Test toggle with empty status (line 94-95)."""
    # Force empty status
    test_charger_legacy._status = {}

    # Mock Update calls
    mock_aioclient.get(f"http://{SERVER_URL}/status", status=200, body='{"state": 1}')
    mock_aioclient.get(
        f"http://{SERVER_URL}/config", status=200, body='{"version": "2.9.1"}'
    )

    # Mock toggle call
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "$FS", "ret": "$OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_legacy.toggle_override()
        assert "Toggling manual override via RAPI. Current state: 1" in caplog.text


async def test_toggle_override_missing_state_after_update(mock_aioclient, caplog):
    """Test toggle when state is still missing after update."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "2.9.0"
    charger._status = {}
    # Mock Update calls with NO state
    mock_aioclient.get(f"http://{SERVER_URL}/status", status=200, body='{"other": 1}')
    mock_aioclient.get(
        f"http://{SERVER_URL}/config", status=200, body='{"version": "2.9.0"}'
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.toggle_override()
    assert "Cannot toggle override: current state is unknown" in caplog.text


async def test_toggle_override_state_zero(mock_aioclient, caplog):
    """Test toggle when state is 0 (Unknown)."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "2.9.0"
    charger._status = {"state": 0}

    # Mock Update calls with STILL 0 state
    mock_aioclient.get(f"http://{SERVER_URL}/status", status=200, body='{"state": 0}')
    mock_aioclient.get(
        f"http://{SERVER_URL}/config", status=200, body='{"version": "2.9.0"}'
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.toggle_override()
    assert "Cannot toggle override: current state is unknown" in caplog.text


async def test_toggle_override_partial_status(mock_aioclient):
    """Test toggle when status exists but state is missing."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "2.9.0"
    charger._status = {"other": 1}  # Existing but incomplete status

    # Mock Refresh/Update
    mock_aioclient.get(f"http://{SERVER_URL}/status", status=200, body='{"state": 254}')
    mock_aioclient.get(
        f"http://{SERVER_URL}/config", status=200, body='{"version": "2.9.0"}'
    )

    # Mock toggle call (RAPI path)
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "$FE", "ret": "$OK"}',
    )

    await charger.toggle_override()
    assert charger._status["state"] == 254


async def test_set_override(
    test_charger,
    test_charger_legacy,
    test_charger_unknown_semver,
    mock_aioclient,
    caplog,
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
        caplog.clear()

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
        caplog.clear()
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
        caplog.clear()
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
        caplog.clear()
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

    await test_charger_legacy.update()
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_legacy.set_override("active")
    assert "Feature not supported for older firmware." in caplog.text

    await test_charger_unknown_semver.update()
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_unknown_semver.set_override("active")
    assert "Feature not supported for older firmware." in caplog.text


async def test_clear_override(
    test_charger, test_charger_legacy, mock_aioclient, caplog
):
    """Test clear override function."""
    await test_charger.update()
    mock_aioclient.delete(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.clear_override()
        assert "Clear response: OK" in caplog.text

    await test_charger_legacy.update()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_legacy.clear_override()
        assert "Feature not supported for older firmware." in caplog.text


async def test_get_override(test_charger, test_charger_legacy, mock_aioclient, caplog):
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

    await test_charger_legacy.update()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_legacy.get_override()
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

    caplog.clear()
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
        assert "Clear response: Clear successful" in caplog.text


async def test_set_override_get_fail(test_charger, mock_aioclient, caplog):
    """Test set_override failure when get() fails."""
    await test_charger.update()
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"ok": false, "msg": "failed"}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await test_charger.set_override("active")
    assert "Failed to retrieve current override state" in caplog.text


async def test_set_override_get_missing_state(test_charger, mock_aioclient, caplog):
    """Test set_override failure when get() returns invalid dict."""
    await test_charger.update()
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"ok": true}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await test_charger.set_override("active")
    assert "Failed to retrieve current override state" in caplog.text


async def test_toggle_override_v2_string_state(
    test_charger_legacy, mock_aioclient, caplog
):
    """Test v4 Status reply with string-based state (coercion)."""
    await test_charger_legacy.update()
    # Mock state as a string
    test_charger_legacy._status["state"] = "254"

    value = {"cmd": "OK", "ret": "$OK"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_legacy.toggle_override()
    assert "Toggling manual override via RAPI. Current state: 254" in caplog.text


async def test_toggle_override_v2_invalid_state(test_charger_legacy, caplog):
    """Test v4 Status reply with invalid state (coercion error)."""
    await test_charger_legacy.update()
    # Mock state as invalid string
    test_charger_legacy._status["state"] = "not-an-int"

    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await test_charger_legacy.toggle_override()
    assert "Cannot toggle override: current state is unknown" in caplog.text
