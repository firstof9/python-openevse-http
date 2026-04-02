"""Tests for Override module."""

import json
import logging
from unittest import mock
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp.client_exceptions import ContentTypeError

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import UnknownError, UnsupportedFeature
from tests.const import (
    SERVER_URL,
    TEST_URL_CONFIG,
    TEST_URL_OVERRIDE,
    TEST_URL_RAPI,
    TEST_URL_STATUS,
)

pytestmark = pytest.mark.asyncio


async def test_toggle_override_base(test_charger, mock_aioclient, caplog):
    """Verify toggle_override correctly sends the manual override request."""
    await test_charger.update()
    test_charger.requester.set_update_callback(None)
    mock_aioclient.patch(
        TEST_URL_OVERRIDE,
        status=200,
        body="OK",
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.toggle_override()
    assert "Toggling manual override http" in caplog.text
    await test_charger.ws_disconnect()


async def test_toggle_override_dev(test_charger_dev, mock_aioclient, caplog):
    """Test toggle override with dev version."""
    await test_charger_dev.update()
    test_charger_dev.requester.set_update_callback(None)
    mock_aioclient.patch(
        TEST_URL_OVERRIDE,
        status=200,
        body="OK",
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_dev.toggle_override()
    assert "Stripping 'dev' from version." in caplog.text
    assert "Toggling manual override http" in caplog.text
    await test_charger_dev.ws_disconnect()


async def test_toggle_override_new(test_charger_new, mock_aioclient, caplog):
    """Test toggle override with new features."""
    await test_charger_new.update()
    test_charger_new.requester.set_update_callback(None)
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
    mock_aioclient.patch(
        TEST_URL_OVERRIDE,
        status=200,
        body="OK",
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.toggle_override()
    assert "Toggling manual override http" in caplog.text

    value["state"] = "disabled"
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.toggle_override()
    assert "Toggling manual override http" in caplog.text
    await test_charger_new.ws_disconnect()


async def test_toggle_override_modified_ver(
    test_charger_modified_ver, mock_aioclient, caplog
):
    """Test toggle override with modified version string."""
    await test_charger_modified_ver.update()
    test_charger_modified_ver.requester.set_update_callback(None)
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
    mock_aioclient.patch(
        TEST_URL_OVERRIDE,
        status=200,
        body="OK",
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.toggle_override()
        assert "Detected firmware: v5.0.1_modified" in caplog.text
        assert "Filtered firmware: 5.0.1" in caplog.text
    await test_charger_modified_ver.ws_disconnect()


async def test_toggle_override_v2(test_charger_legacy, mock_aioclient, caplog):
    """Test legacy toggle override."""
    await test_charger_legacy.update()
    test_charger_legacy.requester._update_callback = None
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
    """Test legacy toggle override error (content error)."""
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
    """Test legacy toggle override failure."""
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
    """Test legacy toggle override transport failure."""
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
    """Verify that toggle_override updates status if it is empty before continuing."""
    # Force empty status
    test_charger_legacy._status = {}

    # Mock Update calls
    mock_aioclient.get(
        f"http://{SERVER_URL}/status", status=200, body='{"state": 1}', repeat=True
    )
    mock_aioclient.get(
        f"http://{SERVER_URL}/config",
        status=200,
        body='{"version": "2.9.1"}',
        repeat=True,
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
    """Ensure toggle_override raises UnknownError if state remains missing after update."""
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
    """Ensure toggle_override raises UnknownError if state is 0 (unknown)."""
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
    """Verify that toggle_override handles status with missing state key by refreshing."""
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


@pytest.mark.parametrize(
    "args, kwargs, expected_log",
    [
        (
            ("active",),
            {},
            "Override data: {'state': 'active', 'charge_current': 0, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}",
        ),
        (
            ("active", 30),
            {},
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}",
        ),
        (
            (),
            {"charge_current": 30},
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}",
        ),
        (
            ("active", 30, 32),
            {},
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}",
        ),
        (
            ("active", 30, 32, 2000),
            {},
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 2000, 'time_limit': 0, 'auto_release': True}",
        ),
        (
            ("active", 30, 32, 2000, 5000),
            {},
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 2000, 'time_limit': 5000, 'auto_release': True}",
        ),
    ],
)
async def test_set_override_success(
    test_charger, mock_aioclient, caplog, args, kwargs, expected_log
):
    """Verify that set_override correctly sends various override parameters to the device."""
    await test_charger.update()
    test_charger.requester._update_callback = None
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
        status = await test_charger.set_override(*args, **kwargs)
        assert status == {"msg": "OK"}
        assert expected_log in caplog.text


async def test_set_override_errors(
    test_charger,
    test_charger_legacy,
    test_charger_unknown_semver,
    mock_aioclient,
    caplog,
):
    """Ensure set_override raises appropriate exceptions for invalid states or unsupported firmware."""
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
    """Verify that clear_override correctly sends the DELETE request to remove manual overrides."""
    await test_charger.update()
    mock_aioclient.delete(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
    )
    # Mock refresh calls
    mock_aioclient.get(TEST_URL_STATUS, status=200, body='{"state": 1}')
    mock_aioclient.get(TEST_URL_CONFIG, status=200, body='{"version": "4.1.0"}')

    with caplog.at_level(logging.DEBUG):
        await test_charger.clear_override()
        assert "Clear response: OK" in caplog.text
        assert "Forced full refresh." in caplog.text

    await test_charger_legacy.update()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_legacy.clear_override()
    assert "Feature not supported for older firmware." in caplog.text


async def test_get_override(test_charger, test_charger_legacy, mock_aioclient, caplog):
    """Verify that get_override correctly retrieves the current manual override configuration."""
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
    """Verify that set_override correctly merges partial updates with current override state."""
    await test_charger.update()
    test_charger.requester._update_callback = None
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
    """Verify that clear_override handles non-JSON responses from the clear endpoint."""
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
    """Verify that manual_override correctly coerces string-based 'active' state to boolean True."""
    # Mock status directly for test
    test_charger_legacy._status["state"] = "254"
    with patch.object(test_charger_legacy, "update", AsyncMock()):
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
    """Verify that manual_override returns False and logs a warning for unexpected state values."""
    # Mock status directly for test
    test_charger_legacy._status["state"] = "not-an-int"
    with patch.object(test_charger_legacy, "update", AsyncMock()):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(UnknownError):
                await test_charger_legacy.toggle_override()
    assert "Cannot toggle override: current state is unknown" in caplog.text


async def test_override_failure_logic(mock_aioclient):
    """Verify 'ok: False' error handling across all override operations."""
    # Initial status/config/override calls for update()
    mock_aioclient.get(
        f"http://{SERVER_URL}/status", status=200, body='{"status": "sleeping"}'
    )
    mock_aioclient.get(
        f"http://{SERVER_URL}/config", status=200, body='{"version": "4.1.0"}'
    )
    mock_aioclient.get(
        f"http://{SERVER_URL}/override",
        status=200,
        body=json.dumps(
            {
                "state": "disabled",
                "charge_current": 0,
                "max_current": 0,
                "energy_limit": 0,
                "time_limit": 0,
                "auto_release": True,
            }
        ),
    )

    charger = OpenEVSE(SERVER_URL)
    await charger.update()

    # 1. set() failure
    mock_aioclient.post(
        f"http://{SERVER_URL}/override",
        status=200,
        body='{"msg": "error", "ok": false}',
    )
    with pytest.raises(UnknownError):
        await charger.set_override(charge_current=16)

    # 2. toggle() failure
    mock_aioclient.patch(
        f"http://{SERVER_URL}/override",
        status=200,
        body='{"msg": "error", "ok": false}',
    )
    with pytest.raises(UnknownError):
        await charger.toggle_override()

    # 3. clear() failure
    mock_aioclient.delete(
        f"http://{SERVER_URL}/override",
        status=200,
        body='{"msg": "error", "ok": false}',
    )
    with pytest.raises(UnknownError):
        await charger.clear_override()


async def test_set_override_post_failure(test_charger, mock_aioclient, caplog):
    """Verify that set_override raises UnknownError when the POST response indicates failure."""
    await test_charger.update()
    test_charger.requester._update_callback = None
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
        body='{"ok": false, "msg": "failed"}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await test_charger.set_override("active")
    assert "Problem setting override." in caplog.text


async def test_clear_override_non_dict_response(test_charger, caplog):
    """Verify that clear_override() handles non-dictionary responses gracefully."""
    with patch.object(test_charger, "_version_check", return_value=True):
        # Mock self.process_request to return a string directly
        with patch.object(
            test_charger, "process_request", AsyncMock(return_value="Not a dictionary")
        ):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(UnknownError):
                    await test_charger.clear_override()
    assert (
        "Unexpected non-dict response clearing override: Not a dictionary"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_toggle_legacy_status_refresh(mock_aioclient, caplog):
    """Verify that toggle() for older firmware unconditionally refreshes status."""
    charger = OpenEVSE(SERVER_URL)
    # Mocking legacy version to ensure the RAPI path is taken
    charger._config["version"] = "2.9.1"
    charger._status = {"state": 1}

    # Mock full refresh calls
    mock_aioclient.get(
        f"http://{SERVER_URL}/status", status=200, body='{"state": 254}', repeat=True
    )
    mock_aioclient.get(
        f"http://{SERVER_URL}/config",
        status=200,
        body='{"version": "2.9.1"}',
        repeat=True,
    )

    # Mock toggle call (RAPI path)
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "$FE", "ret": "$OK"}',
    )

    with caplog.at_level(logging.DEBUG):
        await charger.toggle_override()
        # Should have updated from 1 to 254 before sending $FE
        assert charger._status["state"] == 254
        assert "Toggling manual override via RAPI. Current state: 254" in caplog.text
        assert "Forced full refresh." in caplog.text


@pytest.mark.asyncio
async def test_toggle_override_partial_refresh_success(
    test_charger_legacy, mock_aioclient, caplog
):
    """Verify that toggle_override succeeds if status is available even if update() returns False."""
    # Mock update to return False (simulating e.g. /config failure)
    with patch.object(
        test_charger_legacy, "update", AsyncMock(return_value=False)
    ) as mock_update:
        # Mock toggle call (RAPI path)
        mock_aioclient.post(
            TEST_URL_RAPI,
            status=200,
            body='{"cmd": "$FE", "ret": "$OK"}',
        )
        # Ensure we have a state in status so the toggle continues
        test_charger_legacy._status = {"state": 254}
        await test_charger_legacy.toggle_override()
        assert mock_update.call_count == 2
        mock_update.assert_called_with(force_full=True)

    assert "Toggling manual override via RAPI. Current state: 254" in caplog.text
