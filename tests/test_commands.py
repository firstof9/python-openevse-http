"""Tests for command methods (override, current, charge mode, service level, divert, restart, LED)."""

import json
import logging
from datetime import datetime, timezone
from unittest import mock

import pytest
from aiohttp.client_exceptions import ContentTypeError

import openevsehttp as main
from openevsehttp.exceptions import (
    CommandFailedError,
    FirmwareResolutionError,
    UnknownStateError,
    UnsupportedFeature,
)
from tests.common import load_fixture
from tests.conftest import MockClientSession

pytestmark = pytest.mark.asyncio

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_RAPI = "http://openevse.test.tld/r"
TEST_URL_OVERRIDE = "http://openevse.test.tld/override"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_URL_DIVERT = "http://openevse.test.tld/divertmode"
TEST_URL_RESTART = "http://openevse.test.tld/restart"
TEST_URL_CLAIMS_TARGET = "http://openevse.test.tld/claims/target"
TEST_URL_RELAY_RECOVERY = "http://openevse.test.tld/relay/recovery"
TEST_URL_RELAY_RESET = "http://openevse.test.tld/relay/reset"
TEST_URL_CABLE_TEMP = "http://openevse.test.tld/cabletemp"
TEST_URL_TIME = "http://openevse.test.tld/time"
TEST_URL_SETTIME = "http://openevse.test.tld/settime"
TEST_URL_LOGS = "http://openevse.test.tld/logs"
TEST_URL_CERTIFICATES = "http://openevse.test.tld/certificates"
TEST_URL_RFID_ADD = "http://openevse.test.tld/rfid/add"
TEST_URL_RFID_USERS = "http://openevse.test.tld/rfid/users"
TEST_URL_SCHEDULE = "http://openevse.test.tld/schedule"
TEST_URL_SCHEDULE_PLAN = "http://openevse.test.tld/schedule/plan"
TEST_URL_EMETER = "http://openevse.test.tld/emeter"
SERVER_URL = "openevse.test.tld"


# ── toggle_override ──────────────────────────────────────────────────


async def test_toggle_override(
    test_charger,
    test_charger_dev,
    test_charger_new,
    test_charger_modified_ver,
    mock_aioclient,
    caplog,
):
    """Test toggle_override across firmware versions."""
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
    caplog.clear()

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

    caplog.clear()
    await test_charger_new.update()
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.toggle_override()
    assert "Toggling manual override http" in caplog.text
    await test_charger_new.ws_disconnect()


async def test_set_override_non_dict(test_charger, mock_aioclient, caplog):
    """Test set_override() handles non-dict response from get_override()."""
    test_charger._config = {"version": "4.0.1"}

    mock_aioclient.get(TEST_URL_OVERRIDE, status=200, body="[]")

    with caplog.at_level(logging.ERROR, logger="openevsehttp.commands"):
        with pytest.raises(ValueError, match="Invalid override state response"):
            await test_charger.set_override(state="active")

    assert "Invalid override payload: []" in caplog.text


async def test_set_override_msg_only(test_charger, mock_aioclient, caplog):
    """Test set_override() rejects response from get_override() with only 'msg' key."""
    test_charger._config = {"version": "4.0.1"}

    mock_aioclient.get(TEST_URL_OVERRIDE, status=200, body='{"msg": "OK"}')

    with caplog.at_level(logging.ERROR, logger="openevsehttp.commands"):
        with pytest.raises(ValueError, match="Invalid override state response"):
            await test_charger.set_override(state="active")

    assert "Invalid override payload: {'msg': 'OK'}" in caplog.text


async def test_toggle_override_v2(test_charger_v2, mock_aioclient, caplog):
    """Test toggle_override on V2 firmware."""
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
    """Test toggle_override error handling on V2 firmware."""
    await test_charger_v2.update()
    content_error = mock.Mock()
    content_error.real_url = TEST_URL_RAPI
    mock_aioclient.post(
        TEST_URL_RAPI,
        exception=ContentTypeError(
            content_error,
            history="",
            message="Attempt to decode JSON with unexpected mimetype: text/html",
        ),
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(main.ContentTypeError):
            await test_charger_v2.toggle_override()
    assert (
        "Content error: Attempt to decode JSON with unexpected mimetype: text/html"
        in caplog.text
    )


async def test_toggle_override_v2_fail(test_charger_v2, mock_aioclient, caplog):
    """Test toggle_override RAPI failure on V2 firmware."""
    await test_charger_v2.update()
    value = {"cmd": "NK", "ret": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            CommandFailedError, match="Failed to toggle override via RAPI:"
        ):
            await test_charger_v2.toggle_override()
    assert "Problem toggling override via RAPI: $NK^21" in caplog.text


async def test_toggle_override_fail(test_charger, mock_aioclient, caplog):
    """Test toggle_override HTTP failure."""
    await test_charger.update()
    mock_aioclient.patch(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "failure!"}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(CommandFailedError, match="Failed to toggle override:"):
            await test_charger.toggle_override()
    assert "Problem toggling override: {'msg': 'failure!'}" in caplog.text


async def test_custom_override_success_responses(test_charger, mock_aioclient, caplog):
    """Test override methods accept firmware-specific response strings ("Created", "Updated", "Deleted")."""
    await test_charger.update()

    # 1. toggle_override with "Updated"
    mock_aioclient.patch(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "Updated"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.toggle_override()
    assert "Toggling manual override http" in caplog.text

    # 2. clear_override with "Deleted"
    mock_aioclient.delete(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "Deleted"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.clear_override()
    assert "Clearing manual override http" in caplog.text

    # 3. set_current / set_override with "Created"
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
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "Created"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_current(16)
    assert "Setting current limit to 16" in caplog.text


async def test_toggle_override_refresh_fail(mock_aioclient, caplog):
    """Test toggle_override when state is missing and refresh fails."""
    # Use a fresh charger to avoid fixture mock interference
    charger = main.OpenEVSE(
        "openevse.test.tld", session=MockClientSession(mock_aioclient)
    )
    # Mock status for a v3 firmware (older than 4.0.1)
    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body='{"version": "3.3.1"}',  # Still missing state
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"version": "3.3.1"}',
    )
    # Ensure it doesn't have state and is v3
    charger._status = {}
    charger._config = {"version": "3.3.1"}

    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            UnknownStateError, match=r"Cannot toggle override: unknown charger state\."
        ):
            await charger.toggle_override()
    assert "Cannot toggle override: unknown charger state." in caplog.text


# ── set_current ───────────────────────────────────────────────────────


async def test_set_current(test_charger, mock_aioclient, caplog):
    """Test set_current command."""
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
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_current(12)
    assert "Setting current limit to 12" in caplog.text


async def test_set_current_error(
    test_charger, test_charger_broken, mock_aioclient, caplog
):
    """Test set_current command errors."""
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
        with pytest.raises(ValueError):
            await test_charger.set_current(60)
    assert "Invalid value for current limit: 60" in caplog.text

    with pytest.raises(ValueError, match="Current limit must be an integer, got bool"):
        await test_charger.set_current(True)
    with pytest.raises(ValueError, match="Current limit must be an integer, got float"):
        await test_charger.set_current(12.5)

    await test_charger_broken.update()
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "OK", "ret": "$OK^20"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_broken.set_current(24)
    assert "Unable to find firmware version." in caplog.text


async def test_set_current_http_fail(test_charger, mock_aioclient, caplog):
    """Test set_current HTTP failure."""
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
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "failure!"}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(CommandFailedError):
            await test_charger.set_current(12)
    assert "Problem setting current limit: {'msg': 'failure!'}" in caplog.text


async def test_set_current_v2(
    test_charger_v2, test_charger_dev, mock_aioclient, caplog
):
    """Test set_current command on V2 firmware."""
    await test_charger_v2.update()
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_v2.set_current(12)
    assert "Setting current via RAPI" in caplog.text

    await test_charger_dev.update()
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
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_dev.set_current(12)
    assert "Stripping 'dev' from version." in caplog.text


async def test_set_current_rapi_fail(test_charger_v2, mock_aioclient, caplog):
    """Test set_current RAPI failure."""
    await test_charger_v2.update()
    value = {"cmd": "NK", "ret": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(CommandFailedError):
            await test_charger_v2.set_current(12)
    assert "Problem setting current via RAPI: $NK^21" in caplog.text


# ── set_divertmode (toggle divert) ───────────────────────────────────


async def test_divert_mode_no_config(test_charger):
    """Test divert_mode with no config."""
    test_charger._config = {}
    with pytest.raises(UnknownStateError, match="Missing configuration"):
        await test_charger.divert_mode()


async def test_set_divertmode(
    test_charger_new,
    test_charger_v2,
    test_charger_broken,
    test_charger_unknown_semver,
    mock_aioclient,
    caplog,
):
    """Test v4 set divert mode."""
    await test_charger_new.update()
    value = "Divert Mode changed"
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.divert_mode()
        assert (
            "Connecting to http://openevse.test.tld/config with data: {'divert_enabled': True} rapi: None using method post"
            in caplog.text
        )
        assert "Toggling divert: True" in caplog.text
        assert "Non JSON response: Divert Mode changed" in caplog.text

    caplog.clear()
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    test_charger_new._config["divert_enabled"] = True
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.divert_mode()
        assert "Toggling divert: False" in caplog.text

    caplog.clear()
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    test_charger_new._config["divert_enabled"] = False
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.divert_mode()
        assert "Toggling divert: True" in caplog.text

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    await test_charger_v2.update()
    await test_charger_v2.divert_mode()

    # Test UnsupportedFeature based on version
    # This call does NOT consume a POST mock because it raises early
    await test_charger_broken.update()
    test_charger_broken._config["version"] = "1.0.0"
    with pytest.raises(UnsupportedFeature):
        await test_charger_broken.divert_mode()

    # Test JSON success and cache update
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "OK"}',
    )
    test_charger_new._config["version"] = "2.9.1"
    test_charger_new._config["divert_enabled"] = False
    await test_charger_new.divert_mode()
    assert test_charger_new._config["divert_enabled"] is True

    # Test UnsupportedFeature based on missing config key
    # This call DOES NOT consume a POST mock because it raises early
    test_charger_new._config["version"] = "4.1.2"
    del test_charger_new._config["divert_enabled"]
    with pytest.raises(UnsupportedFeature):
        await test_charger_new.divert_mode()
    await test_charger_unknown_semver.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_unknown_semver.divert_mode()
    assert "Non-semver firmware version detected" in caplog.text


async def test_set_divertmode_dict(test_charger_new, mock_aioclient):
    """Test set_divertmode with dict response."""
    mock_aioclient.post(
        "http://openevse.test.tld/divertmode",
        status=200,
        body='{"msg": "OK"}',
    )
    await test_charger_new.set_divert_mode("eco")


async def test_set_divertmode_fail(test_charger_new, mock_aioclient):
    """Test set_divertmode failure."""
    mock_aioclient.post(
        "http://openevse.test.tld/divertmode",
        status=200,
        body='{"msg": "failure!"}',
    )
    with pytest.raises(main.CommandFailedError):
        await test_charger_new.set_divert_mode("eco")


# ── set_charge_mode ──────────────────────────────────────────────────


async def test_set_charge_mode(test_charger, mock_aioclient, caplog):
    """Test set_charge_mode command."""
    await test_charger.update()
    value = {"msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_charge_mode("eco")

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
    value = {"config_version": 2, "msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_charge_mode("fast")

    value = {"msg": "error"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with pytest.raises(CommandFailedError):
        with caplog.at_level(logging.DEBUG):
            await test_charger.set_charge_mode("fast")
    assert "Problem issuing command: {'msg': 'error'}" in caplog.text

    value = {"msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with pytest.raises(ValueError):
        await test_charger.set_charge_mode("test")
    await test_charger.ws_disconnect()


# ── set_service_level ────────────────────────────────────────────────


async def test_set_service_level(test_charger, mock_aioclient, caplog):
    """Test set service level."""
    await test_charger.update()
    value = {"msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_service_level(1)

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
    value = {"config_version": 2, "msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_service_level(2)

    value = {"msg": "error"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with pytest.raises(CommandFailedError):
        with caplog.at_level(logging.DEBUG):
            await test_charger.set_service_level(1)
    assert "Problem issuing command: {'msg': 'error'}" in caplog.text

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "done"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_service_level("A")
    assert "Set service level to: A" in caplog.text

    with pytest.raises(ValueError):
        await test_charger.set_service_level("B")
    await test_charger.ws_disconnect()


# ── restart ──────────────────────────────────────────────────────────


async def test_restart_wifi(test_charger_modified_ver, mock_aioclient, caplog):
    """Test restart_wifi sends restart request and logs response."""
    await test_charger_modified_ver.update()
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body='{"result": "OK", "msg": "restart gateway ok"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.restart_wifi()
    assert "Restart response: restart gateway" in caplog.text

    # Also verify standard ESP32 gateway response `{"msg": "restart gateway"}`
    caplog.clear()
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body='{"msg": "restart gateway"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.restart_wifi()
    assert "WiFi Restart response: restart gateway" in caplog.text


async def test_restart_wifi_fail(test_charger, mock_aioclient, caplog):
    """Test restart_wifi failure."""
    await test_charger.update()
    # Test Mapping failure (result != OK and success is False)
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body='{"result": "error", "success": false, "msg": "failed"}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(CommandFailedError, match="Failed to restart WiFi: failed"):
            await test_charger.restart_wifi()
    assert (
        "Problem restarting WiFi: {'result': 'error', 'success': False, 'msg': 'failed'}"
        in caplog.text
    )

    # Test Non-Mapping failure (returning a list)
    caplog.clear()
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body="[]",
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            CommandFailedError, match="Failed to restart WiFi: Unknown error"
        ):
            await test_charger.restart_wifi()
    assert "Problem restarting WiFi: []" in caplog.text

    # Test Mapping failure (result == OK but msg doesn't contain OK)
    caplog.clear()
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body='{"result": "OK", "msg": "failed completely"}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            CommandFailedError, match="Failed to restart WiFi: failed completely"
        ):
            await test_charger.restart_wifi()
    assert (
        "Problem restarting WiFi: {'result': 'OK', 'msg': 'failed completely'}"
        in caplog.text
    )


async def test_evse_restart(
    test_charger_v2, test_charger_modified_ver, mock_aioclient, caplog
):
    """Test EVSE module restart."""
    await test_charger_v2.update()
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_v2.restart_evse()
    assert "EVSE Restart response: $OK^20" in caplog.text
    caplog.clear()

    await test_charger_modified_ver.update()
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body='{"msg": "restart evse"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.restart_evse()
    assert "Restarting EVSE module via HTTP" in caplog.text
    caplog.clear()


async def test_evse_restart_fail(test_charger_v2, mock_aioclient, caplog):
    """Test EVSE module restart failure."""
    await test_charger_v2.update()
    value = {"cmd": "NK", "ret": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            CommandFailedError, match="Failed to restart EVSE module via RAPI:"
        ):
            await test_charger_v2.restart_evse()
    assert "Problem restarting EVSE module via RAPI: $NK^21" in caplog.text
    caplog.clear()


async def test_restart_evse_http_failure(test_charger, mock_aioclient):
    """Test restart_evse HTTP failure detection."""
    # Force version check to >= 5.0.0
    test_charger._config["version"] = "5.0.0"

    # 1. Test False reply
    mock_aioclient.post(TEST_URL_RESTART, status=200, body="false")
    with pytest.raises(
        CommandFailedError,
        match=r"Failed to restart EVSE module via HTTP: \{'msg': False\}",
    ):
        await test_charger.restart_evse()

    # 2. Test NK message
    mock_aioclient.post(TEST_URL_RESTART, status=200, body='{"msg": "NK"}')
    with pytest.raises(
        CommandFailedError,
        match=r"Failed to restart EVSE module via HTTP: \{'msg': 'NK'\}",
    ):
        await test_charger.restart_evse()

    # 3. Test RAPI Error in msg
    from openevsehttp.const import RAPI_ERRORS

    error_msg = RAPI_ERRORS[0]
    mock_aioclient.post(
        TEST_URL_RESTART, status=200, body=json.dumps({"msg": error_msg})
    )
    with pytest.raises(
        CommandFailedError,
        match=f"Failed to restart EVSE module via HTTP: {{'msg': '{error_msg}'}}",
    ):
        await test_charger.restart_evse()


# ── set_divert_mode ──────────────────────────────────────────────────


async def test_set_divert_mode(
    test_charger_new, test_charger_v2, mock_aioclient, caplog
):
    """Test set_divert_mode reply."""
    await test_charger_new.update()
    value = "Divert Mode changed"
    mock_aioclient.post(
        TEST_URL_DIVERT,
        status=200,
        body=value,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.set_divert_mode("fast")
    assert "Setting divert mode to fast" in caplog.text

    mock_aioclient.post(
        TEST_URL_DIVERT,
        status=200,
        body=value,
    )
    await test_charger_v2.update()
    with caplog.at_level(logging.DEBUG):
        await test_charger_v2.set_divert_mode("eco")
    assert "Setting divert mode to eco" in caplog.text

    with pytest.raises(ValueError):
        with caplog.at_level(logging.DEBUG):
            await test_charger_new.set_divert_mode("test")
    assert "Invalid value for divert mode: test" in caplog.text

    mock_aioclient.post(
        TEST_URL_DIVERT,
        status=200,
        body="error",
    )
    with pytest.raises(CommandFailedError):
        with caplog.at_level(logging.DEBUG):
            await test_charger_new.set_divert_mode("fast")
    assert "Problem issuing command: error" in caplog.text


# ── LED brightness ───────────────────────────────────────────────────


async def test_led_brightness(test_charger_new, test_charger_v2, caplog):
    """Test led_brightness reply."""
    await test_charger_new.update()
    status = test_charger_new.led_brightness
    assert status == 125

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            _ = test_charger_v2.led_brightness
    assert "Feature not supported for older firmware." in caplog.text


async def test_set_led_brightness(
    test_charger_new, test_charger_v2, mock_aioclient, caplog
):
    """Test set_led_brightness reply."""
    await test_charger_new.update()
    value = '{"msg": "OK"}'
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.set_led_brightness(255)
    assert "Setting LED brightness to 255" in caplog.text

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.set_led_brightness(255)
    assert (
        "set_led_brightness requires gateway firmware 4.1.0 or higher." in caplog.text
    )


async def test_set_led_brightness_fail(test_charger_new, mock_aioclient, caplog):
    """Test set_led_brightness failure."""
    await test_charger_new.update()
    value = '{"msg": "failure!"}'
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(CommandFailedError):
            await test_charger_new.set_led_brightness(255)
    assert "Problem issuing command: {'msg': 'failure!'}" in caplog.text


async def test_set_led_brightness_validation(test_charger):
    """Test set_led_brightness input validation."""
    # 1. Test non-int (bool)
    with pytest.raises(TypeError, match="LED brightness must be an integer, got bool"):
        await test_charger.set_led_brightness(True)

    # 2. Test non-int (str)
    with pytest.raises(TypeError, match="LED brightness must be an integer, got str"):
        await test_charger.set_led_brightness("100")

    # 3. Test out of range (low)
    with pytest.raises(
        ValueError, match=r"LED brightness -1 is out of range \(0-255\)"
    ):
        await test_charger.set_led_brightness(-1)

    # 4. Test out of range (high)
    with pytest.raises(
        ValueError, match=r"LED brightness 256 is out of range \(0-255\)"
    ):
        await test_charger.set_led_brightness(256)


# ── async_charge_current / async_override_state ──────────────────────


async def test_async_charge_current(
    test_charger, test_charger_v2, mock_aioclient, caplog
):
    """Test async_charge_current function."""
    await test_charger.update()
    mock_aioclient.get(
        TEST_URL_CLAIMS_TARGET,
        status=200,
        body='{"properties":{"state":"disabled","charge_current":28,"max_current":23,"auto_release":false},"claims":{"state":65540,"charge_current":65537,"max_current":65548}}',
        repeat=False,
    )

    value = await test_charger.get_charge_current()
    assert value == 28

    mock_aioclient.get(
        TEST_URL_CLAIMS_TARGET,
        status=200,
        body='{"properties":{"state":"disabled","max_current":23,"auto_release":false},"claims":{"state":65540,"charge_current":65537,"max_current":65548}}',
        repeat=False,
    )

    value = await test_charger.get_charge_current()
    assert value == 48
    await test_charger.ws_disconnect()

    await test_charger_v2.update()
    value = await test_charger_v2.get_charge_current()
    assert value == 25
    await test_charger_v2.ws_disconnect()


async def test_async_charge_current_list(test_charger, mock_aioclient):
    """Test async_charge_current function with a list of claims."""
    await test_charger.update()
    # Mock a list-based response
    mock_aioclient.get(
        TEST_URL_CLAIMS_TARGET,
        status=200,
        body='[{"properties":{"state":"disabled","charge_current":30,"max_current":23,"auto_release":false}}]',
        repeat=False,
    )

    value = await test_charger.get_charge_current()
    assert value == 30
    await test_charger.ws_disconnect()


async def test_async_charge_current_list_multi(test_charger, mock_aioclient):
    """Test async_charge_current function with a list of claims, searching for charge_current."""
    await test_charger.update()
    # Mock a list-based response where the first claim doesn't have charge_current
    mock_aioclient.get(
        TEST_URL_CLAIMS_TARGET,
        status=200,
        body='[{"properties":{"state":"disabled"}}, {"properties":{"charge_current":35}}]',
        repeat=False,
    )

    value = await test_charger.get_charge_current()
    assert value == 35
    await test_charger.ws_disconnect()


async def test_async_override_state(
    test_charger, test_charger_v2, mock_aioclient, caplog
):
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
        status = await test_charger.get_override_state()
        assert status == "active"

    value = {
        "state": "disabled",
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        status = await test_charger.get_override_state()
        assert status == "disabled"

    value = {}
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        status = await test_charger.get_override_state()
        assert status == "auto"

    with caplog.at_level(logging.DEBUG):
        await test_charger_v2.update()
        await test_charger_v2.get_override_state()
        assert "Override state unavailable on older firmware." in caplog.text


async def test_set_override_auto_release(test_charger_new, mock_aioclient):
    """Test set_override with auto_release provided."""
    await test_charger_new.update()
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"state":"active","auto_release":true}',
    )
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg":"OK"}',
    )
    await test_charger_new.set_override(auto_release=False)


async def test_normalize_response(test_charger):
    """Test _normalize_response helper."""
    # Test with dict
    assert test_charger._normalize_response({"msg": "OK"}) == {"msg": "OK"}
    # Test with string
    assert test_charger._normalize_response("OK") == {"msg": "OK"}


# ── update_firmware ──────────────────────────────────────────────────


async def test_update_firmware_bytes(test_charger, mock_aioclient, caplog):
    """Test update_firmware with bytes upload."""
    test_charger._config["version"] = "4.1.7"
    mock_aioclient.post(
        "http://openevse.test.tld/update",
        status=200,
        body="OK",
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger.update_firmware(firmware_bytes=b"fakebinarydata")
        assert response == "OK"
        assert (
            "Uploading firmware binary to http://openevse.test.tld/update (14 bytes)"
            in caplog.text
        )
        assert "Firmware upload request completed. Response: OK" in caplog.text
        assert "Firmware update started, setting ota_update flag." in caplog.text
        assert test_charger.ota_update is True


async def test_update_firmware_url(test_charger, mock_aioclient, caplog):
    """Test update_firmware with a direct URL."""
    test_charger._config["version"] = "4.1.7"
    mock_aioclient.post(
        "http://openevse.test.tld/update",
        status=200,
        body='{"msg":"started"}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger.update_firmware(
            firmware_url="http://github.com/release.bin"
        )
        assert response == {"msg": "started"}
        assert (
            "Requesting OpenEVSE to download and update from: http://github.com/release.bin"
            in caplog.text
        )
        assert (
            "Firmware update request completed. Response: {'msg': 'started'}"
            in caplog.text
        )
        assert "Firmware update started, setting ota_update flag." in caplog.text
        assert test_charger.ota_update is True


async def test_update_firmware_auto(test_charger, mock_aioclient, caplog):
    """Test update_firmware with auto-resolved URL from GitHub."""
    # Setup config with a buildenv and version >= 4.1.7
    test_charger._config = {"version": "4.1.7", "buildenv": "openevse_esp32-gateway"}

    # Mock GitHub Releases API to return assets matching buildenv
    github_response = {
        "tag_name": "v4.1.2",
        "body": "release notes",
        "html_url": "https://github.com/OpenEVSE/releases/v4.1.2",
        "assets": [
            {
                "name": "openevse_esp32-gateway.bin",
                "browser_download_url": "https://github.com/OpenEVSE/releases/download/v4.1.2/openevse_esp32-gateway.bin",
            },
            {
                "name": "other_env.bin",
                "browser_download_url": "https://github.com/OpenEVSE/releases/download/v4.1.2/other_env.bin",
            },
        ],
    }

    mock_aioclient.get(
        "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest",
        status=200,
        body=json.dumps(github_response),
    )

    mock_aioclient.post(
        "http://openevse.test.tld/update",
        status=200,
        body='{"msg":"started"}',
    )

    with caplog.at_level(logging.DEBUG):
        response = await test_charger.update_firmware()
        assert response == {"msg": "started"}
        assert (
            "No firmware URL provided. Resolving latest matching firmware from GitHub."
            in caplog.text
        )
        assert "Detected firmware: 4.1.7" in caplog.text
        assert "Using version: 4.1.7" in caplog.text
        assert (
            "Firmware check URL: https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest"
            in caplog.text
        )
        assert "Firmware check response status: 200" in caplog.text
        assert (
            "GitHub release metadata successfully fetched for version: v4.1.2"
            in caplog.text
        )
        assert (
            "Matching buildenv 'openevse_esp32-gateway' against assets" in caplog.text
        )
        assert (
            "Found matching firmware asset: https://github.com/OpenEVSE/releases/download/v4.1.2/openevse_esp32-gateway.bin"
            in caplog.text
        )
        assert (
            "Requesting OpenEVSE to download and update from: https://github.com/OpenEVSE/releases/download/v4.1.2/openevse_esp32-gateway.bin"
            in caplog.text
        )
        assert (
            "Firmware update request completed. Response: {'msg': 'started'}"
            in caplog.text
        )
        assert "Firmware update started, setting ota_update flag." in caplog.text
        assert test_charger.ota_update is True


async def test_update_firmware_auto_github_token(test_charger, mock_aioclient):
    """Test update_firmware forwards github_token to firmware_check."""
    test_charger._config = {"version": "4.1.7", "buildenv": "openevse_esp32-gateway"}
    github_response = {
        "tag_name": "v4.1.2",
        "body": "release notes",
        "html_url": "https://github.com/OpenEVSE/releases/v4.1.2",
        "assets": [
            {
                "name": "openevse_esp32-gateway.bin",
                "browser_download_url": "https://github.com/OpenEVSE/releases/download/v4.1.2/openevse_esp32-gateway.bin",
            },
        ],
    }
    url = "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest"
    mock_aioclient.get(url, status=200, body=json.dumps(github_response))
    mock_aioclient.post(
        "http://openevse.test.tld/update",
        status=200,
        body='{"msg":"started"}',
    )

    response = await test_charger.update_firmware(github_token="ghp_firmwaretoken")
    assert response == {"msg": "started"}
    last_github_call = [call for call in mock_aioclient.requests if call[1] == url][-1]
    assert last_github_call[2]["headers"]["Authorization"] == "Bearer ghp_firmwaretoken"


async def test_update_firmware_auto_missing_buildenv(
    test_charger, mock_aioclient, caplog
):
    """Test update_firmware raises RuntimeError when buildenv asset is missing."""
    test_charger._config = {"version": "4.1.7", "buildenv": "openevse_esp32-gateway"}

    # Mock GitHub releases but without the matching gateway asset
    github_response = {
        "tag_name": "v4.1.2",
        "body": "release notes",
        "html_url": "https://github.com/OpenEVSE/releases/v4.1.2",
        "assets": [
            {
                "name": "other_env.bin",
                "browser_download_url": "https://github.com/OpenEVSE/releases/download/v4.1.2/other_env.bin",
            }
        ],
    }

    mock_aioclient.get(
        "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest",
        status=200,
        body=json.dumps(github_response),
    )

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(
            FirmwareResolutionError,
            match=r"Could not resolve latest firmware download URL from GitHub\.",
        ):
            await test_charger.update_firmware()
        assert (
            "Could not find asset matching target filename 'openevse_esp32-gateway.bin' in assets: ['other_env.bin']"
            in caplog.text
        )
        assert (
            "Could not resolve latest firmware download URL from GitHub." in caplog.text
        )


async def test_update_firmware_both_provided(test_charger, caplog):
    """Test update_firmware raises ValueError when both bytes and URL are provided."""
    test_charger._config["version"] = "4.1.7"
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError):
            await test_charger.update_firmware(
                firmware_url="http://url", firmware_bytes=b"bytes"
            )
        assert "Cannot specify both firmware_bytes and firmware_url" in caplog.text


async def test_update_firmware_url_invalid(test_charger, caplog):
    """Test update_firmware raises ValueError when firmware_url is empty or invalid type."""
    test_charger._config["version"] = "4.1.7"
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError):
            await test_charger.update_firmware(firmware_url="")
        assert "Invalid firmware_url: " in caplog.text

        with pytest.raises(ValueError):
            await test_charger.update_firmware(firmware_url="   ")
        assert "Invalid firmware_url:    " in caplog.text

        with pytest.raises(ValueError):
            await test_charger.update_firmware(firmware_url=123)  # type: ignore
        assert "Invalid firmware_url: 123" in caplog.text


async def test_update_firmware_unsupported(test_charger):
    """Test update_firmware raises UnsupportedFeature on older firmware."""
    test_charger._config["version"] = "4.1.2"
    with pytest.raises(UnsupportedFeature):
        await test_charger.update_firmware(firmware_url="http://url")


async def test_update_firmware_error_response(test_charger, mock_aioclient, caplog):
    """Test update_firmware doesn't set ota_update on error responses."""
    test_charger._config["version"] = "4.1.7"
    test_charger._status = {}
    mock_aioclient.post(
        "http://openevse.test.tld/update",
        status=200,
        body='{"msg":"error"}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger.update_firmware(
            firmware_url="http://github.com/release.bin"
        )
        assert response == {"msg": "error"}
        assert (
            "Firmware update response did not indicate start: {'msg': 'error'}"
            in caplog.text
        )
        assert test_charger.ota_update is False


async def test_update_firmware_assets_invalid_type(
    test_charger, mock_aioclient, caplog
):
    """Test update_firmware handles non-list assets gracefully."""
    test_charger._config = {"version": "4.1.7", "buildenv": "openevse_esp32-gateway"}

    # Mock GitHub releases but with assets as a dict (invalid type)
    github_response = {
        "tag_name": "v4.1.2",
        "body": "release notes",
        "html_url": "https://github.com/OpenEVSE/releases/v4.1.2",
        "assets": {"name": "not_a_list"},
    }

    mock_aioclient.get(
        "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest",
        status=200,
        body=json.dumps(github_response),
    )

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(
            FirmwareResolutionError,
            match=r"Could not resolve latest firmware download URL from GitHub\.",
        ):
            await test_charger.update_firmware()
        assert "Invalid GitHub assets payload: {'name': 'not_a_list'}" in caplog.text


async def test_update_firmware_assets_invalid_item(
    test_charger, mock_aioclient, caplog
):
    """Test update_firmware handles non-mapping assets gracefully."""
    test_charger._config = {"version": "4.1.7", "buildenv": "openevse_esp32-gateway"}

    # Mock GitHub releases with assets list containing non-mapping elements (e.g., a string)
    github_response = {
        "tag_name": "v4.1.2",
        "body": "release notes",
        "html_url": "https://github.com/OpenEVSE/releases/v4.1.2",
        "assets": [
            "invalid_asset_string",
            {
                "name": "openevse_esp32-gateway.bin",
                "browser_download_url": "http://url",
            },
        ],
    }

    mock_aioclient.get(
        "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest",
        status=200,
        body=json.dumps(github_response),
    )

    mock_aioclient.post(
        "http://openevse.test.tld/update",
        status=200,
        body='{"msg":"started"}',
    )

    with caplog.at_level(logging.DEBUG):
        response = await test_charger.update_firmware()
        assert response == {"msg": "started"}
        assert "Found matching firmware asset: http://url" in caplog.text


async def test_update_firmware_bytes_empty(test_charger, caplog):
    """Test update_firmware raises ValueError when empty firmware_bytes are provided."""
    test_charger._config["version"] = "4.1.7"
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError):
            await test_charger.update_firmware(firmware_bytes=b"")
        assert "Empty firmware bytes provided" in caplog.text


async def test_set_mqtt_vehicle_range_miles(test_charger_new, mock_aioclient, caplog):
    """Test set_mqtt_vehicle_range_miles command."""
    await test_charger_new.update()
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.set_mqtt_vehicle_range_miles(True)
    assert "Setting mqtt_vehicle_range_miles to True" in caplog.text

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.set_mqtt_vehicle_range_miles(False)
    assert "Setting mqtt_vehicle_range_miles to False" in caplog.text

    with pytest.raises(TypeError, match=r"Value must be a boolean\."):
        await test_charger_new.set_mqtt_vehicle_range_miles("invalid")

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(CommandFailedError):
        await test_charger_new.set_mqtt_vehicle_range_miles(True)


async def test_set_rfid_enabled(test_charger, test_charger_new, mock_aioclient, caplog):
    """Test set_rfid_enabled command."""
    # Version gate check on older firmware
    await test_charger.update()
    with pytest.raises(UnsupportedFeature):
        await test_charger.set_rfid_enabled(True)

    await test_charger_new.update()
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.set_rfid_enabled(True)
    assert "Setting rfid_enabled to True" in caplog.text
    assert test_charger_new._config["rfid_enabled"] is True

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.set_rfid_enabled(False)
    assert "Setting rfid_enabled to False" in caplog.text
    assert test_charger_new._config["rfid_enabled"] is False

    with pytest.raises(TypeError, match=r"Value must be a boolean\."):
        await test_charger_new.set_rfid_enabled("invalid")  # type: ignore[arg-type]

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(CommandFailedError):
        await test_charger_new.set_rfid_enabled(True)


# ── run_stuck_relay_recovery ─────────────────────────────────────────


async def test_run_stuck_relay_recovery_http(test_charger_new, mock_aioclient, caplog):
    """Test run_stuck_relay_recovery via HTTP on v5.1.0+ with controller 9.3.0+."""
    await test_charger_new.update()

    # Older controller firmware (< 9.3.0) raises UnsupportedFeature
    with pytest.raises(
        UnsupportedFeature, match="requires OpenEVSE controller firmware 9.3.0"
    ):
        await test_charger_new.run_stuck_relay_recovery()

    # Update controller firmware to 9.3.0
    test_charger_new._config["firmware"] = "9.3.0"

    # Success
    mock_aioclient.post(
        TEST_URL_RELAY_RECOVERY,
        status=200,
        body='{"msg": "done"}',
        headers={"Content-Type": "application/json"},
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.run_stuck_relay_recovery()
    assert "Running stuck-relay recovery via HTTP" in caplog.text
    last_req = mock_aioclient.requests[-1]
    headers = last_req[2].get("headers", {})
    assert headers.get("X-Requested-With") == "OpenEVSE"
    assert "python-openevse-http" in headers.get("User-Agent", "")

    # Failure
    mock_aioclient.post(
        TEST_URL_RELAY_RECOVERY,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem running stuck-relay recovery"
    ):
        await test_charger_new.run_stuck_relay_recovery()


async def test_run_stuck_relay_recovery_rapi(test_charger, mock_aioclient, caplog):
    """Test run_stuck_relay_recovery via RAPI on older gateway firmware with controller 9.3.0+."""
    await test_charger.update()

    # Controller firmware 7.1.3 (< 9.3.0) raises UnsupportedFeature
    with pytest.raises(
        UnsupportedFeature, match="requires OpenEVSE controller firmware 9.3.0"
    ):
        await test_charger.run_stuck_relay_recovery()

    # Update controller firmware to 9.3.1
    test_charger._config["firmware"] = "9.3.1"

    # Success
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "OK", "ret": "$OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.run_stuck_relay_recovery()
    assert "Running stuck-relay recovery via RAPI" in caplog.text

    # Failure ($NK when EV is connected)
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "NK", "ret": "$NK"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem running stuck-relay recovery via RAPI"
    ):
        await test_charger.run_stuck_relay_recovery()

    # Failure (RAPI queue error)
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": false, "msg": "RAPI_RESPONSE_QUEUE_FULL"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem running stuck-relay recovery via RAPI"
    ):
        await test_charger.run_stuck_relay_recovery()


# ── reset_relay_health ───────────────────────────────────────────────


async def test_reset_relay_health_http(test_charger_new, mock_aioclient, caplog):
    """Test reset_relay_health via HTTP on v5.1.0+ with controller 9.3.0+."""
    await test_charger_new.update()

    # Older controller firmware (< 9.3.0) raises UnsupportedFeature
    with pytest.raises(
        UnsupportedFeature, match="requires OpenEVSE controller firmware 9.3.0"
    ):
        await test_charger_new.reset_relay_health()

    # Update controller firmware to 9.3.0
    test_charger_new._config["firmware"] = "9.3.0"

    # Success
    mock_aioclient.post(
        TEST_URL_RELAY_RESET,
        status=200,
        body='{"msg": "done"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.reset_relay_health()
    assert "Resetting relay health via HTTP" in caplog.text
    last_req = mock_aioclient.requests[-1]
    headers = last_req[2].get("headers", {})
    assert headers.get("X-Requested-With") == "OpenEVSE"
    assert "python-openevse-http" in headers.get("User-Agent", "")

    # Failure
    mock_aioclient.post(
        TEST_URL_RELAY_RESET,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(CommandFailedError, match="Problem resetting relay health"):
        await test_charger_new.reset_relay_health()


async def test_reset_relay_health_rapi(test_charger, mock_aioclient, caplog):
    """Test reset_relay_health via RAPI on older gateway firmware with controller 9.3.0+."""
    await test_charger.update()

    # Controller firmware 7.1.3 (< 9.3.0) raises UnsupportedFeature
    with pytest.raises(
        UnsupportedFeature, match="requires OpenEVSE controller firmware 9.3.0"
    ):
        await test_charger.reset_relay_health()

    # Update controller firmware to 9.3.0
    test_charger._config["firmware"] = "9.3.0"

    # Success
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "OK", "ret": "$OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.reset_relay_health()
    assert "Resetting relay health via RAPI" in caplog.text

    # Failure ($NK)
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "NK", "ret": "$NK"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem resetting relay health via RAPI"
    ):
        await test_charger.reset_relay_health()

    # Failure (RAPI queue error)
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": false, "msg": "RAPI_RESPONSE_TIMEOUT"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem resetting relay health via RAPI"
    ):
        await test_charger.reset_relay_health()


# ── cable_temp ───────────────────────────────────────────────────────


async def test_get_cable_temp(test_charger, test_charger_new, mock_aioclient, caplog):
    """Test get_cable_temp endpoint."""
    await test_charger.update()

    # Controller firmware < 9.4.0 raises UnsupportedFeature
    with pytest.raises(
        UnsupportedFeature, match="requires OpenEVSE controller firmware 9.4.0"
    ):
        await test_charger.get_cable_temp()

    test_charger._config["firmware"] = "9.4.0"
    # Gateway firmware < 5.1.0 raises UnsupportedFeature
    with pytest.raises(UnsupportedFeature, match="requires gateway firmware 5.1.0"):
        await test_charger.get_cable_temp()

    await test_charger_new.update()
    test_charger_new._config["firmware"] = "9.4.0"

    # Success
    payload = {
        "supported": True,
        "enabled": True,
        "sources": [
            {
                "source": 0,
                "name": "ev1",
                "pin": 2,
                "status": 0,
                "temperature": 45.2,
                "r25": 10000,
                "beta": 3443,
                "offset_c10": 0,
                "panic_c10": 900,
            }
        ],
    }
    mock_aioclient.get(
        TEST_URL_CABLE_TEMP,
        status=200,
        body=json.dumps(payload),
    )
    result = await test_charger_new.get_cable_temp()
    assert result["supported"] is True
    assert result["sources"][0]["name"] == "ev1"

    # Invalid non-dict response
    mock_aioclient.get(
        TEST_URL_CABLE_TEMP,
        status=200,
        body="invalid non json",
    )
    with pytest.raises(CommandFailedError, match="Invalid response from /cabletemp"):
        await test_charger_new.get_cable_temp()


async def test_set_cable_temp(test_charger, test_charger_new, mock_aioclient):
    """Test set_cable_temp command."""
    await test_charger.update()
    with pytest.raises(
        UnsupportedFeature, match="requires OpenEVSE controller firmware 9.4.0"
    ):
        await test_charger.set_cable_temp(0, 1)

    test_charger._config["firmware"] = "9.4.0"
    with pytest.raises(UnsupportedFeature, match="requires gateway firmware 5.1.0"):
        await test_charger.set_cable_temp(0, 1)

    await test_charger_new.update()
    test_charger_new._config["firmware"] = "9.4.0"

    # Input validation
    with pytest.raises(ValueError, match="source must be an integer between 0 and 3"):
        await test_charger_new.set_cable_temp(4, 1)
    with pytest.raises(ValueError, match="source must be an integer between 0 and 3"):
        await test_charger_new.set_cable_temp(True, 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="pin must be an integer between 0 and 2"):
        await test_charger_new.set_cable_temp(0, 3)

    # Incomplete calibration parameters
    with pytest.raises(ValueError, match="must all be provided together"):
        await test_charger_new.set_cable_temp(0, 1, r25=10000, beta=3443)

    # Type check calibration parameters
    with pytest.raises(TypeError, match="r25 must be an integer"):
        await test_charger_new.set_cable_temp(
            0,
            1,
            r25="bad",
            beta=3443,
            offset_c10=0,
            panic_c10=900,  # type: ignore[arg-type]
        )

    # Success pin only
    mock_aioclient.post(
        TEST_URL_CABLE_TEMP,
        status=200,
        body='{"msg": "done"}',
    )
    await test_charger_new.set_cable_temp(0, 2)
    last_req = mock_aioclient.requests[-1]
    assert last_req[2]["json"] == {"source": 0, "pin": 2}
    headers = last_req[2].get("headers", {})
    assert headers.get("X-Requested-With") == "OpenEVSE"
    assert "python-openevse-http" in headers.get("User-Agent", "")

    # Success full calibration
    mock_aioclient.post(
        TEST_URL_CABLE_TEMP,
        status=200,
        body='{"msg": "done"}',
    )
    await test_charger_new.set_cable_temp(
        0, 2, r25=10000, beta=3443, offset_c10=5, panic_c10=900
    )
    last_req = mock_aioclient.requests[-1]
    assert last_req[2]["json"] == {
        "source": 0,
        "pin": 2,
        "r25": 10000,
        "beta": 3443,
        "offset_c10": 5,
        "panic_c10": 900,
    }

    # Failure response
    mock_aioclient.post(
        TEST_URL_CABLE_TEMP,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem configuring cable temperature"
    ):
        await test_charger_new.set_cable_temp(0, 2)


async def test_set_cable_temp_enabled(test_charger, test_charger_new, mock_aioclient):
    """Test set_cable_temp_enabled command."""
    await test_charger.update()
    with pytest.raises(
        UnsupportedFeature, match="requires OpenEVSE controller firmware 9.4.0"
    ):
        await test_charger.set_cable_temp_enabled(True)

    await test_charger_new.update()
    test_charger_new._config["firmware"] = "9.4.0"

    with pytest.raises(TypeError, match="Value must be a boolean"):
        await test_charger_new.set_cable_temp_enabled("invalid")  # type: ignore[arg-type]

    # Success
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "OK"}',
    )
    await test_charger_new.set_cable_temp_enabled(True)
    assert test_charger_new._config["cable_temp"] is True

    # Failure
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(CommandFailedError, match="Problem toggling cable_temp"):
        await test_charger_new.set_cable_temp_enabled(False)


# ── time endpoints (/time, /settime, sync_time) ──────────────────────


async def test_get_time(test_charger, test_charger_v2, mock_aioclient):
    """Test get_time across firmware versions."""
    await test_charger.update()

    # Success on v4.x
    mock_aioclient.get(
        TEST_URL_TIME,
        status=200,
        body=json.dumps(
            {
                "time": "2026-03-25T15:30:00Z",
                "offset": "-0700",
                "time_zone": "America/Phoenix|MST7",
                "sntp_enabled": True,
            }
        ),
    )
    res = await test_charger.get_time()
    assert res["time"] == "2026-03-25T15:30:00Z"
    assert res["offset"] == "-0700"
    assert res["sntp_enabled"] is True

    # Invalid response on v4.x
    mock_aioclient.get(
        TEST_URL_TIME,
        status=200,
        body="invalid json string",
    )
    with pytest.raises(CommandFailedError, match="Invalid response from /time"):
        await test_charger.get_time()

    # Legacy fallback on v2.x
    await test_charger_v2.update()
    legacy_time = await test_charger_v2.get_time()
    assert legacy_time["time"] is None
    assert legacy_time["offset"] is None


async def test_set_time_v4(test_charger, mock_aioclient):
    """Test set_time on v4.x firmware."""
    await test_charger.update()

    # Invalid argument types
    with pytest.raises(TypeError, match="sntp must be a boolean"):
        await test_charger.set_time(sntp="yes")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="timezone_str must be a string"):
        await test_charger.set_time(timezone_str=123)  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="target_time must be a datetime or ISO-8601 string"
    ):
        await test_charger.set_time(target_time=12345)  # type: ignore[arg-type]

    # Success with datetime object
    mock_aioclient.post(
        TEST_URL_TIME,
        status=200,
        body='{"msg": "done"}',
    )
    dt = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    await test_charger.set_time(
        target_time=dt,
        timezone_str="UTC0",
        sntp=False,
    )
    assert test_charger._config["sntp_enabled"] is False
    assert test_charger._config["time_zone"] == "UTC0"

    # Success with string and default sntp
    mock_aioclient.post(
        TEST_URL_TIME,
        status=200,
        body='{"msg": "set"}',
    )
    await test_charger.set_time(
        target_time="2026-03-25T12:00:00Z",
        timezone_str="America/New_York|EST5EDT",
        sntp=True,
    )
    assert test_charger._config["sntp_enabled"] is True
    assert test_charger._config["time_zone"] == "America/New_York|EST5EDT"

    # Success with target_time=None and sntp=False (auto UTC now)
    mock_aioclient.post(
        TEST_URL_TIME,
        status=200,
        body='{"msg": "done"}',
    )
    await test_charger.set_time(sntp=False)

    # Failure response
    mock_aioclient.post(
        TEST_URL_TIME,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(CommandFailedError, match="Problem setting time"):
        await test_charger.set_time(sntp=True)


async def test_set_time_v3(test_charger, mock_aioclient):
    """Test set_time on legacy v3.x firmware using /settime."""
    await test_charger.update()
    test_charger._config["version"] = "3.3.1"

    # Invalid target_time
    with pytest.raises(
        TypeError, match="target_time must be a datetime or ISO-8601 string"
    ):
        await test_charger.set_time(target_time=12345)  # type: ignore[arg-type]

    # Success with datetime and sntp=False
    mock_aioclient.post(
        TEST_URL_SETTIME,
        status=200,
        body='{"msg": "done"}',
    )
    dt = datetime(2026, 3, 25, 15, 0, 0, tzinfo=timezone.utc)
    await test_charger.set_time(target_time=dt, timezone_str="UTC0", sntp=False)

    # Success with sntp=False and target_time=None
    mock_aioclient.post(
        TEST_URL_SETTIME,
        status=200,
        body='{"msg": "set"}',
    )
    await test_charger.set_time(sntp=False)

    # Failure response
    mock_aioclient.post(
        TEST_URL_SETTIME,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(CommandFailedError, match="Problem setting time"):
        await test_charger.set_time(sntp=False)


async def test_set_time_v2(test_charger_v2, mock_aioclient):
    """Test set_time fallback to RAPI $S1 on legacy v2.x firmware."""
    await test_charger_v2.update()

    # Invalid string format
    with pytest.raises(ValueError, match="Could not parse date string"):
        await test_charger_v2.set_time(target_time="not-a-date")

    with pytest.raises(
        TypeError, match="target_time must be a datetime or ISO-8601 string"
    ):
        await test_charger_v2.set_time(target_time=9999)  # type: ignore[arg-type]

    # Success with string
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "OK", "ret": "$OK"}',
    )
    await test_charger_v2.set_time(target_time="2026-03-25T15:30:45Z")

    # Success with datetime
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "OK", "ret": "$OK"}',
    )
    dt = datetime(2026, 3, 25, 15, 30, 45, tzinfo=timezone.utc)
    await test_charger_v2.set_time(target_time=dt)

    # Success with target_time=None (auto UTC now)
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "OK", "ret": "$OK"}',
    )
    await test_charger_v2.set_time(target_time=None)

    # Failure with RAPI rejection
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "NK", "ret": "$NK"}',
    )
    with pytest.raises(CommandFailedError, match="Problem setting RTC via RAPI"):
        await test_charger_v2.set_time(target_time=dt)


async def test_sync_time_unsupported(test_charger_v2):
    """Test sync_time on older firmware raises UnsupportedFeature."""
    await test_charger_v2.update()
    with pytest.raises(
        UnsupportedFeature, match="sync_time requires gateway firmware 4.0.0 or higher"
    ):
        await test_charger_v2.sync_time()


async def test_sync_time(test_charger, mock_aioclient):
    """Test sync_time command on supported firmware."""
    await test_charger.update()

    # Success
    mock_aioclient.post(
        TEST_URL_TIME,
        status=200,
        body='{"msg": "done"}',
    )
    await test_charger.sync_time()

    # Failure
    mock_aioclient.post(
        TEST_URL_TIME,
        status=200,
        body='{"msg": "error"}',
    )
    with pytest.raises(CommandFailedError, match="Problem triggering NTP sync"):
        await test_charger.sync_time()


# ── logs endpoint (/logs, /logs/{index}) ─────────────────────────────


async def test_get_logs_unsupported(test_charger_v2):
    """Test get_logs on older firmware raises UnsupportedFeature."""
    await test_charger_v2.update()
    with pytest.raises(
        UnsupportedFeature, match="get_logs requires gateway firmware 4.0.0 or higher"
    ):
        await test_charger_v2.get_logs()


async def test_get_logs(test_charger, mock_aioclient):
    """Test get_logs endpoint on supported firmware."""
    await test_charger.update()

    # Invalid index type
    with pytest.raises(TypeError, match="index must be an integer"):
        await test_charger.get_logs(index="0")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="index must be an integer"):
        await test_charger.get_logs(index=True)  # type: ignore[arg-type]

    # Success: block index range (index is None)
    mock_aioclient.get(
        TEST_URL_LOGS,
        status=200,
        body=json.dumps({"min": 0, "max": 15}),
    )
    res_range = await test_charger.get_logs()
    assert res_range == {"min": 0, "max": 15}

    # Invalid non-dict response for block index range
    mock_aioclient.get(
        TEST_URL_LOGS,
        status=200,
        body="invalid response",
    )
    with pytest.raises(CommandFailedError, match="Invalid response from /logs"):
        await test_charger.get_logs()

    # Success: specific log event block
    events = [
        {
            "time": "2026-03-25T15:30:00Z",
            "type": "notification",
            "evseState": 1,
            "pilot": 32,
            "energy": 12500,
        },
        {
            "time": "2026-03-25T15:35:00Z",
            "type": "information",
            "evseState": 2,
            "pilot": 32,
            "energy": 12600,
        },
    ]
    mock_aioclient.get(
        f"{TEST_URL_LOGS}/2",
        status=200,
        body=json.dumps(events),
    )
    res_events = await test_charger.get_logs(index=2)
    assert len(res_events) == 2
    assert res_events[0]["type"] == "notification"
    assert res_events[1]["pilot"] == 32

    # Invalid non-list response for specific block
    mock_aioclient.get(
        f"{TEST_URL_LOGS}/3",
        status=200,
        body='{"msg": "not a list"}',
    )
    with pytest.raises(CommandFailedError, match="Invalid response from /logs/3"):
        await test_charger.get_logs(index=3)


# ── certificates ─────────────────────────────────────────────────────


async def test_certificates_unsupported(test_charger_v2):
    """Test certificate methods on older firmware raise UnsupportedFeature."""
    await test_charger_v2.update()

    with pytest.raises(
        UnsupportedFeature,
        match="get_certificates requires gateway firmware 4.0.0 or higher",
    ):
        await test_charger_v2.get_certificates()

    with pytest.raises(
        UnsupportedFeature,
        match="get_root_ca requires gateway firmware 4.0.0 or higher",
    ):
        await test_charger_v2.get_root_ca()

    with pytest.raises(
        UnsupportedFeature,
        match="add_certificate requires gateway firmware 4.0.0 or higher",
    ):
        await test_charger_v2.add_certificate("test", "cert")

    with pytest.raises(
        UnsupportedFeature,
        match="delete_certificate requires gateway firmware 4.0.0 or higher",
    ):
        await test_charger_v2.delete_certificate("133e62267a1a5cf8")


async def test_get_certificates(test_charger, mock_aioclient, caplog):
    """Test get_certificates for all certificates and specific certificate."""
    await test_charger.update()

    # 1. Validation errors
    with pytest.raises(TypeError, match="certificate_id must be a non-empty string"):
        await test_charger.get_certificates(certificate_id="")
    with pytest.raises(TypeError, match="certificate_id must be a non-empty string"):
        await test_charger.get_certificates(certificate_id=123)  # type: ignore

    # 2. Get all certificates list
    certs_list = [
        {
            "id": "133e62267a1a5cf8",
            "type": "client",
            "name": "Self Signed Test",
            "certificate": "-----BEGIN CERTIFICATE-----\n...",
            "key": "__REDACTED__",
        },
        {
            "id": "1154b5ac394",
            "type": "root",
            "name": "GlobalSign",
            "certificate": "-----BEGIN CERTIFICATE-----\n...",
        },
    ]
    mock_aioclient.get(
        TEST_URL_CERTIFICATES,
        status=200,
        body=json.dumps(certs_list),
    )
    with caplog.at_level(logging.DEBUG):
        result = await test_charger.get_certificates()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["id"] == "133e62267a1a5cf8"
    assert "Querying certificates: http://openevse.test.tld/certificates" in caplog.text

    # 3. Invalid non-list response for all certificates
    mock_aioclient.get(
        TEST_URL_CERTIFICATES,
        status=200,
        body='{"msg": "unexpected dict"}',
    )
    with pytest.raises(CommandFailedError, match="Invalid response from /certificates"):
        await test_charger.get_certificates()

    # 4. Get specific certificate by ID
    single_cert = certs_list[0]
    mock_aioclient.get(
        f"{TEST_URL_CERTIFICATES}/133e62267a1a5cf8",
        status=200,
        body=json.dumps(single_cert),
    )
    with caplog.at_level(logging.DEBUG):
        single_res = await test_charger.get_certificates(
            certificate_id="133e62267a1a5cf8"
        )
    assert isinstance(single_res, dict)
    assert single_res["name"] == "Self Signed Test"

    # 5. Invalid non-dict response for single certificate
    mock_aioclient.get(
        f"{TEST_URL_CERTIFICATES}/bad_cert",
        status=200,
        body="[1, 2, 3]",
    )
    with pytest.raises(
        CommandFailedError, match="Invalid response from /certificates/bad_cert"
    ):
        await test_charger.get_certificates(certificate_id="bad_cert")


async def test_get_root_ca(test_charger, mock_aioclient, caplog):
    """Test get_root_ca retrieving root CA bundle text."""
    await test_charger.update()

    pem_bundle = (
        "-----BEGIN CERTIFICATE-----\nROOT_CA_1\n-----END CERTIFICATE-----\n"
        "-----BEGIN CERTIFICATE-----\nROOT_CA_2\n-----END CERTIFICATE-----\n"
    )
    mock_aioclient.get(
        f"{TEST_URL_CERTIFICATES}/root",
        status=200,
        body=pem_bundle,
    )
    with caplog.at_level(logging.DEBUG):
        root_ca = await test_charger.get_root_ca()
    assert root_ca == pem_bundle
    assert "Querying root CA certificates" in caplog.text

    # Invalid non-str response
    mock_aioclient.get(
        f"{TEST_URL_CERTIFICATES}/root",
        status=200,
        body='{"error": "bad"}',
    )
    # Note: If JSON body is returned and auto-parsed as dict, get_root_ca raises CommandFailedError
    with pytest.raises(
        CommandFailedError, match="Invalid response from /certificates/root"
    ):
        await test_charger.get_root_ca()


async def test_add_certificate(test_charger, mock_aioclient, caplog):
    """Test add_certificate for root CA and client cert with private key."""
    await test_charger.update()

    # 1. Type validation
    with pytest.raises(TypeError, match="name must be a non-empty string"):
        await test_charger.add_certificate("", "cert")
    with pytest.raises(TypeError, match="certificate must be a non-empty string"):
        await test_charger.add_certificate("test", "")
    with pytest.raises(TypeError, match="key must be a non-empty string or None"):
        await test_charger.add_certificate("test", "cert", key="")

    # 2. Add root certificate (no key)
    mock_aioclient.post(
        TEST_URL_CERTIFICATES,
        status=200,
        body='{"id": "1154b5ac394", "msg": "done"}',
    )
    with caplog.at_level(logging.DEBUG):
        res = await test_charger.add_certificate(
            name="My Root CA", certificate="-----BEGIN CERTIFICATE-----\n..."
        )
    assert res["id"] == "1154b5ac394"
    assert res["msg"] == "done"
    assert "Adding certificate 'My Root CA'" in caplog.text

    # 3. Add client certificate (with key)
    mock_aioclient.post(
        TEST_URL_CERTIFICATES,
        status=200,
        body='{"id": "133e62267a1a5cf8", "msg": "done"}',
    )
    res_client = await test_charger.add_certificate(
        name="Client Cert",
        certificate="-----BEGIN CERTIFICATE-----\n...",
        key="-----BEGIN PRIVATE KEY-----\n...",
    )
    assert res_client["id"] == "133e62267a1a5cf8"

    # 4. Error response
    mock_aioclient.post(
        TEST_URL_CERTIFICATES,
        status=200,
        body='{"msg": "Could not add certificate"}',
    )
    with pytest.raises(
        CommandFailedError,
        match="Problem adding certificate: {'msg': 'Could not add certificate'}",
    ):
        await test_charger.add_certificate("bad", "bad_cert")


async def test_delete_certificate(test_charger, mock_aioclient, caplog):
    """Test delete_certificate."""
    await test_charger.update()

    # 1. Type validation
    with pytest.raises(TypeError, match="certificate_id must be a non-empty string"):
        await test_charger.delete_certificate("")
    with pytest.raises(TypeError, match="certificate_id must be a non-empty string"):
        await test_charger.delete_certificate(12345)  # type: ignore

    # 2. Successful deletion
    mock_aioclient.delete(
        f"{TEST_URL_CERTIFICATES}/133e62267a1a5cf8",
        status=200,
        body='{"msg": "done"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.delete_certificate("133e62267a1a5cf8")
    assert (
        "Deleting certificate http://openevse.test.tld/certificates/133e62267a1a5cf8"
        in caplog.text
    )

    # 3. Failed deletion
    mock_aioclient.delete(
        f"{TEST_URL_CERTIFICATES}/not_found",
        status=404,
        body='{"msg": "Not found"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem deleting certificate: {'msg': 'Not found'}"
    ):
        await test_charger.delete_certificate("not_found")


# ── rfid endpoints ───────────────────────────────────────────────────


async def test_add_rfid_tag(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test add_rfid_tag."""
    await test_charger.update()
    await test_charger_v2.update()

    # 1. Firmware version check (requires >= 4.0.0)
    with pytest.raises(
        UnsupportedFeature, match="add_rfid_tag requires gateway firmware 4.0.0"
    ):
        await test_charger_v2.add_rfid_tag()

    # 2. Successful add tag mode
    mock_aioclient.post(
        TEST_URL_RFID_ADD,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.add_rfid_tag()
    assert (
        "Triggering RFID add tag mode: http://openevse.test.tld/rfid/add" in caplog.text
    )

    # 3. Failed add tag mode
    mock_aioclient.post(
        TEST_URL_RFID_ADD,
        status=500,
        body='{"msg": "Failed"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem adding RFID tag: {'msg': 'Failed'}"
    ):
        await test_charger.add_rfid_tag()


async def test_get_rfid_users(test_charger, test_charger_new, mock_aioclient, caplog):
    """Test get_rfid_users."""
    await test_charger.update()
    await test_charger_new.update()

    # 1. Firmware version check (requires >= 5.0.0)
    with pytest.raises(
        UnsupportedFeature, match="get_rfid_users requires gateway firmware 5.0.0"
    ):
        await test_charger.get_rfid_users()

    # 2. Successful fetch
    users_data = {
        "01020304": "Alice",
        "05060708": "Bob",
    }
    mock_aioclient.get(
        TEST_URL_RFID_USERS,
        status=200,
        body=json.dumps(users_data),
    )
    with caplog.at_level(logging.DEBUG):
        result = await test_charger_new.get_rfid_users()
    assert result == {"01020304": "Alice", "05060708": "Bob"}
    assert "Fetching RFID users from http://openevse.test.tld/rfid/users" in caplog.text

    # 3. Invalid non-mapping response
    mock_aioclient.get(
        TEST_URL_RFID_USERS,
        status=200,
        body="invalid",
    )
    with pytest.raises(
        CommandFailedError,
        match="Invalid response format for /rfid/users: invalid",
    ):
        await test_charger_new.get_rfid_users()


async def test_set_rfid_user(test_charger, test_charger_new, mock_aioclient, caplog):
    """Test set_rfid_user."""
    await test_charger.update()
    await test_charger_new.update()

    # 1. Firmware version check (requires >= 5.0.0)
    with pytest.raises(
        UnsupportedFeature, match="set_rfid_user requires gateway firmware 5.0.0"
    ):
        await test_charger.set_rfid_user("01020304", "Alice")

    # 2. Input validation
    with pytest.raises(TypeError, match="rfid must be a non-empty string."):
        await test_charger_new.set_rfid_user("", "Alice")
    with pytest.raises(TypeError, match="rfid must be a non-empty string."):
        await test_charger_new.set_rfid_user(12345, "Alice")  # type: ignore
    with pytest.raises(TypeError, match="name must be a non-empty string."):
        await test_charger_new.set_rfid_user("01020304", "")
    with pytest.raises(TypeError, match="name must be a non-empty string."):
        await test_charger_new.set_rfid_user("01020304", None)  # type: ignore

    # 3. Successful set user
    mock_aioclient.post(
        TEST_URL_RFID_USERS,
        status=200,
        body='{"msg": "User name saved"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.set_rfid_user("01020304", "Alice")
    assert "Setting RFID user 'Alice' for tag '01020304'" in caplog.text

    # 4. Failed set user
    mock_aioclient.post(
        TEST_URL_RFID_USERS,
        status=500,
        body='{"msg": "Failed"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem setting RFID user: {'msg': 'Failed'}"
    ):
        await test_charger_new.set_rfid_user("01020304", "Alice")


async def test_delete_rfid_user(test_charger, test_charger_new, mock_aioclient, caplog):
    """Test delete_rfid_user."""
    await test_charger.update()
    await test_charger_new.update()

    # 1. Firmware version check (requires >= 5.0.0)
    with pytest.raises(
        UnsupportedFeature, match="delete_rfid_user requires gateway firmware 5.0.0"
    ):
        await test_charger.delete_rfid_user("01020304")

    # 2. Input validation
    with pytest.raises(TypeError, match="rfid must be a non-empty string."):
        await test_charger_new.delete_rfid_user("")
    with pytest.raises(TypeError, match="rfid must be a non-empty string."):
        await test_charger_new.delete_rfid_user(12345)  # type: ignore

    # 3. Successful delete user
    mock_aioclient.delete(
        f"{TEST_URL_RFID_USERS}?rfid=01020304",
        status=200,
        body='{"msg": "User name removed"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.delete_rfid_user("01020304")
    assert "Deleting RFID user for tag '01020304'" in caplog.text

    # 4. Failed delete user
    mock_aioclient.delete(
        f"{TEST_URL_RFID_USERS}?rfid=01020304",
        status=500,
        body='{"msg": "Failed"}',
    )
    with pytest.raises(
        CommandFailedError, match="Problem deleting RFID user: {'msg': 'Failed'}"
    ):
        await test_charger_new.delete_rfid_user("01020304")


# ── schedule commands ────────────────────────────────────────────────


async def test_get_schedule(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test get_schedule across scenarios."""
    await test_charger.update()
    await test_charger_v2.update()

    # 1. Firmware version check (requires >= 4.0.0)
    with pytest.raises(
        UnsupportedFeature, match="get_schedule requires gateway firmware 4.0.0"
    ):
        await test_charger_v2.get_schedule()

    # 2. Input validation for event_id
    with pytest.raises(TypeError, match="event_id must be an integer."):
        await test_charger.get_schedule(event_id="invalid")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="event_id must be an integer."):
        await test_charger.get_schedule(event_id=True)  # type: ignore[arg-type]

    # 3. GET /schedule success (list of events)
    schedule_data = [
        {"id": 1, "state": "active", "time": "01:00:00", "days": ["Monday", "Tuesday"]},
        {
            "id": 2,
            "state": "disabled",
            "time": "06:00:00",
            "days": ["Monday", "Tuesday"],
        },
    ]
    mock_aioclient.get(
        TEST_URL_SCHEDULE,
        status=200,
        body=json.dumps(schedule_data),
    )
    with caplog.at_level(logging.DEBUG):
        result = await test_charger.get_schedule()
    assert result == schedule_data
    assert "Getting schedule from http://openevse.test.tld/schedule" in caplog.text

    # 4. GET /schedule/{event_id} success (single event dict)
    single_event = {
        "id": 1,
        "state": "active",
        "time": "01:00:00",
        "days": ["Monday", "Tuesday"],
    }
    mock_aioclient.get(
        f"{TEST_URL_SCHEDULE}/1",
        status=200,
        body=json.dumps(single_event),
    )
    result_event = await test_charger.get_schedule(event_id=1)
    assert result_event == single_event

    # 5. GET /schedule/{event_id} not found
    mock_aioclient.get(
        f"{TEST_URL_SCHEDULE}/99",
        status=404,
        body='{"msg":"Not found"}',
    )
    with pytest.raises(
        CommandFailedError, match="Schedule event not found: {'msg': 'Not found'}"
    ):
        await test_charger.get_schedule(event_id=99)

    # 6. Fallback from GET (405 Method Not Allowed) to POST
    mock_aioclient.get(
        TEST_URL_SCHEDULE,
        status=405,
        body='{"msg":"Method not allowed"}',
    )
    mock_aioclient.post(
        TEST_URL_SCHEDULE,
        status=200,
        body=json.dumps(schedule_data),
    )
    result_fallback = await test_charger.get_schedule()
    assert result_fallback == schedule_data

    # 7. Invalid non-collection response format
    mock_aioclient.get(
        TEST_URL_SCHEDULE,
        status=200,
        body="invalid",
    )
    with pytest.raises(
        CommandFailedError, match="Invalid response format for /schedule: invalid"
    ):
        await test_charger.get_schedule()


async def test_set_schedule(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test set_schedule across scenarios."""
    await test_charger.update()
    await test_charger_v2.update()

    # 1. Firmware version check (requires >= 4.0.0)
    with pytest.raises(
        UnsupportedFeature, match="set_schedule requires gateway firmware 4.0.0"
    ):
        await test_charger_v2.set_schedule(
            {"state": "active", "time": "01:00:00", "days": ["Monday"]}
        )

    # 2. Input validation
    with pytest.raises(TypeError, match="event_id must be an integer."):
        await test_charger.set_schedule({"state": "active"}, event_id="invalid")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="event_id must be an integer."):
        await test_charger.set_schedule({"state": "active"}, event_id=False)  # type: ignore[arg-type]
    with pytest.raises(
        TypeError, match="event must be a mapping when event_id is specified."
    ):
        await test_charger.set_schedule(["not", "a", "mapping"], event_id=1)  # type: ignore[arg-type]
    with pytest.raises(
        TypeError, match="event must be a mapping or a list of mappings."
    ):
        await test_charger.set_schedule("invalid_event")  # type: ignore[arg-type]

    # 3. Successful POST /schedule (single event)
    event_payload = {
        "id": 1,
        "state": "active",
        "time": "02:00:00",
        "days": ["Wednesday"],
    }
    mock_aioclient.post(
        TEST_URL_SCHEDULE,
        status=200,
        body='{"msg": "done"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_schedule(event_payload)
    assert "Setting schedule on http://openevse.test.tld/schedule" in caplog.text

    # 4. Successful POST /schedule/{event_id} (update specific event)
    mock_aioclient.post(
        f"{TEST_URL_SCHEDULE}/1",
        status=200,
        body='{"msg": "done"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_schedule(event_payload, event_id=1)
    assert "Setting schedule on http://openevse.test.tld/schedule/1" in caplog.text

    # 5. Successful POST /schedule (batch list of events)
    batch_payload = [
        {"id": 1, "state": "active", "time": "01:00:00", "days": ["Monday"]},
        {"id": 2, "state": "disabled", "time": "07:00:00", "days": ["Monday"]},
    ]
    mock_aioclient.post(
        TEST_URL_SCHEDULE,
        status=200,
        body='{"msg": "done"}',
    )
    await test_charger.set_schedule(batch_payload)

    # 6. Successful POST /schedule with empty list (clearing schedule batch)
    mock_aioclient.post(
        TEST_URL_SCHEDULE,
        status=200,
        body='{"msg": "done"}',
    )
    await test_charger.set_schedule([])

    # 7. Failed POST /schedule
    mock_aioclient.post(
        TEST_URL_SCHEDULE,
        status=500,
        body='{"msg": "Could not parse JSON"}',
    )
    with pytest.raises(
        CommandFailedError,
        match="Problem setting schedule: {'msg': 'Could not parse JSON'}",
    ):
        await test_charger.set_schedule(event_payload)


async def test_delete_schedule(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test delete_schedule across scenarios."""
    await test_charger.update()
    await test_charger_v2.update()

    # 1. Firmware version check (requires >= 4.0.0)
    with pytest.raises(
        UnsupportedFeature, match="delete_schedule requires gateway firmware 4.0.0"
    ):
        await test_charger_v2.delete_schedule(1)

    # 2. Input validation
    with pytest.raises(TypeError, match="event_id must be an integer."):
        await test_charger.delete_schedule("1")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="event_id must be an integer."):
        await test_charger.delete_schedule(True)  # type: ignore[arg-type]

    # 3. Successful DELETE /schedule/{event_id}
    mock_aioclient.delete(
        f"{TEST_URL_SCHEDULE}/1",
        status=200,
        body='{"msg": "done"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.delete_schedule(1)
    assert (
        "Deleting schedule event 1 on http://openevse.test.tld/schedule/1"
        in caplog.text
    )

    # 4. Failed DELETE (404 Not found)
    mock_aioclient.delete(
        f"{TEST_URL_SCHEDULE}/99",
        status=404,
        body='{"msg": "Not found"}',
    )
    with pytest.raises(
        CommandFailedError,
        match="Problem deleting schedule event 99: {'msg': 'Not found'}",
    ):
        await test_charger.delete_schedule(99)


async def test_get_schedule_plan(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test get_schedule_plan across scenarios."""
    await test_charger.update()
    await test_charger_v2.update()

    # 1. Firmware version check (requires >= 4.1.0)
    with pytest.raises(
        UnsupportedFeature, match="get_schedule_plan requires gateway firmware 4.1.0"
    ):
        await test_charger_v2.get_schedule_plan()

    # 2. Successful GET /schedule/plan
    plan_data = {
        "current_day": "Monday",
        "current_offset": 3600,
        "next_event_delay": 7200,
        "current_event": {
            "id": 1,
            "state": "active",
            "time": "01:00:00",
            "day": "Monday",
        },
        "next_event": {
            "id": 2,
            "state": "disabled",
            "time": "03:00:00",
            "day": "Monday",
        },
        "Monday": [{"id": 1, "state": "active", "time": "01:00:00"}],
    }
    mock_aioclient.get(
        TEST_URL_SCHEDULE_PLAN,
        status=200,
        body=json.dumps(plan_data),
    )
    with caplog.at_level(logging.DEBUG):
        result = await test_charger.get_schedule_plan()
    assert result == plan_data
    assert (
        "Getting schedule plan from http://openevse.test.tld/schedule/plan"
        in caplog.text
    )

    # 3. Invalid non-mapping response
    mock_aioclient.get(
        TEST_URL_SCHEDULE_PLAN,
        status=200,
        body="invalid",
    )
    with pytest.raises(
        CommandFailedError, match="Invalid response format for /schedule/plan: invalid"
    ):
        await test_charger.get_schedule_plan()


# ── reset_energy_meter ───────────────────────────────────────────────


async def test_reset_energy_meter(
    test_charger, test_charger_v2, mock_aioclient, caplog
):
    """Test reset_energy_meter command."""
    await test_charger.update()

    # 1. Version check failure on older firmware
    with pytest.raises(
        UnsupportedFeature, match="reset_energy_meter requires gateway firmware 4.0.0"
    ):
        await test_charger_v2.reset_energy_meter()

    # 2. Successful reset with default params (hard=False, import=False)
    mock_aioclient.delete(
        TEST_URL_EMETER,
        status=200,
        body='{"msg": "Reset done"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.reset_energy_meter()
    assert (
        "Resetting energy meter: http://openevse.test.tld/emeter (hard=False, import=False)"
        in caplog.text
    )

    # 3. Successful reset with hard=True, import_from_evse=True
    caplog.clear()
    mock_aioclient.delete(
        TEST_URL_EMETER,
        status=200,
        body='{"msg": "Reset done"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.reset_energy_meter(hard=True, import_from_evse=True)
    assert (
        "Resetting energy meter: http://openevse.test.tld/emeter (hard=True, import=True)"
        in caplog.text
    )

    # 4. Failure response from firmware
    mock_aioclient.delete(
        TEST_URL_EMETER,
        status=200,
        body='{"msg": "Reset failed"}',
    )
    with pytest.raises(CommandFailedError, match="Problem resetting energy meter"):
        await test_charger.reset_energy_meter()

    # 5. Non-mapping / error response
    mock_aioclient.delete(
        TEST_URL_EMETER,
        status=200,
        body="invalid response",
    )
    with pytest.raises(CommandFailedError, match="Problem resetting energy meter"):
        await test_charger.reset_energy_meter()
