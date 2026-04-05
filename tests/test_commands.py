"""Tests for command methods (override, current, charge mode, service level, divert, restart, LED)."""

import json
import logging
from unittest import mock

import pytest
from aiohttp.client_exceptions import ContentTypeError

import openevsehttp.__main__ as main
from openevsehttp.exceptions import (
    UnknownError,
    UnsupportedFeature,
)
from tests.common import load_fixture

pytestmark = pytest.mark.asyncio

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_RAPI = "http://openevse.test.tld/r"
TEST_URL_OVERRIDE = "http://openevse.test.tld/override"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_URL_DIVERT = "http://openevse.test.tld/divertmode"
TEST_URL_RESTART = "http://openevse.test.tld/restart"
TEST_URL_CLAIMS_TARGET = "http://openevse.test.tld/claims/target"
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
        with pytest.raises(main.ContentTypeError):
            await test_charger_v2.toggle_override()
    assert (
        "Content error: Attempt to decode JSON with unexpected mimetype: text/html"
        in caplog.text
    )


# ── set_current ───────────────────────────────────────────────────────


async def test_set_current(test_charger, mock_aioclient, caplog):
    """Test v4 Status reply."""
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
    """Test v4 Status reply."""
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

    await test_charger_broken.update()
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body='{"cmd": "OK", "ret": "$OK^20"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_broken.set_current(24)
    assert "Unable to find firmware version." in caplog.text


async def test_set_current_v2(
    test_charger_v2, test_charger_dev, mock_aioclient, caplog
):
    """Test v4 Status reply."""
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


# ── set_divertmode (toggle divert) ───────────────────────────────────


async def test_divert_mode_no_config(test_charger):
    """Test divert_mode with no config."""
    test_charger._config = {}
    with pytest.raises(RuntimeError, match="Missing configuration"):
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

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    test_charger_new._config["divert_enabled"] = True
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.divert_mode()
        assert "Toggling divert: False" in caplog.text

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
    assert "Non-semver firmware version detected." in caplog.text


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
    with pytest.raises(main.UnknownError):
        await test_charger_new.set_divert_mode("eco")


# ── set_charge_mode ──────────────────────────────────────────────────


async def test_set_charge_mode(test_charger, mock_aioclient, caplog):
    """Test v4 Status reply."""
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
    with pytest.raises(UnknownError):
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
    with pytest.raises(UnknownError):
        with caplog.at_level(logging.DEBUG):
            await test_charger.set_service_level(1)
    assert "Problem issuing command: {'msg': 'error'}" in caplog.text

    value = {"msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with pytest.raises(ValueError):
        await test_charger.set_service_level("A")
    await test_charger.ws_disconnect()


# ── restart ──────────────────────────────────────────────────────────


async def test_restart_wifi(test_charger_modified_ver, mock_aioclient, caplog):
    """Test v4 set divert mode."""
    await test_charger_modified_ver.update()
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body='{"msg": "restart gateway"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.restart_wifi()
    assert "Restart response: restart gateway" in caplog.text


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

    await test_charger_modified_ver.update()
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body='{"msg": "restart evse"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.restart_evse()
    assert "Restarting EVSE module via HTTP" in caplog.text


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
    with pytest.raises(UnknownError):
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
    assert "Feature not supported for older firmware." in caplog.text


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
