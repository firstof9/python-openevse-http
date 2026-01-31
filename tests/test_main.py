"""Library tests."""

import asyncio
import json
import logging
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from datetime import datetime, timezone, timedelta
from freezegun import freeze_time
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from aiohttp.client_reqrep import ConnectionKey
from awesomeversion.exceptions import AwesomeVersionCompareException

import openevsehttp.__main__ as main
from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import (
    InvalidType,
    MissingSerial,
    UnknownError,
    UnsupportedFeature,
)
from openevsehttp.websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
)
from tests.common import load_fixture

pytestmark = pytest.mark.asyncio

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_RAPI = "http://openevse.test.tld/r"
TEST_URL_OVERRIDE = "http://openevse.test.tld/override"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_URL_DIVERT = "http://openevse.test.tld/divertmode"
TEST_URL_RESTART = "http://openevse.test.tld/restart"
TEST_URL_LIMIT = "http://openevse.test.tld/limit"
TEST_URL_WS = "ws://openevse.test.tld/ws"
TEST_URL_CLAIMS = "http://openevse.test.tld/claims"
TEST_URL_CLAIMS_TARGET = "http://openevse.test.tld/claims/target"
TEST_URL_GITHUB_v4 = (
    "https://api.github.com/repos/OpenEVSE/ESP32_WiFi_V4.x/releases/latest"
)
TEST_URL_GITHUB_v2 = (
    "https://api.github.com/repos/OpenEVSE/ESP8266_WiFi_v2.x/releases/latest"
)
SERVER_URL = "openevse.test.tld"


async def test_get_status_auth(test_charger_auth):
    """Test v4 Status reply."""
    await test_charger_auth.update()
    status = test_charger_auth.status
    assert status == "sleeping"
    await test_charger_auth.ws_disconnect()


async def test_ws_state(test_charger):
    """Test v4 Status reply."""
    await test_charger.update()
    value = test_charger.ws_state
    assert value == STATE_DISCONNECTED
    await test_charger.ws_disconnect()


async def test_update_status(test_charger):
    """Test v4 Status reply."""
    data = json.loads(load_fixture("v4_json/status.json"))
    await test_charger._update_status("data", data, None)
    assert test_charger._status == data


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
        exception=TimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(TimeoutError):
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


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 220), ("test_charger_v2", 220)],
    indirect=["charger"],
)
async def test_get_ammeter_scale_factor(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.ammeter_scale_factor
    assert status == expected
    await charger.ws_disconnect()


# Checks don't seem to be working
# async def test_get_temp_check_enabled(fixture, expected, request):
#     """Test v4 Status reply."""
#     status = fixture, expected, request.temp_check_enabled
#     assert status


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 2), ("test_charger_v2", 2)],
    indirect=["charger"],
)
async def test_get_service_level(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.service_level
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 240), ("test_charger_v2", 240)],
    indirect=["charger"],
)
async def test_get_charging_voltage(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.charging_voltage
    assert status == expected


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", "STA"), ("test_charger_v2", "STA")],
    indirect=["charger"],
)
async def test_get_mode(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.mode
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", False), ("test_charger_v2", False)],
    indirect=["charger"],
)
async def test_get_using_ethernet(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.using_ethernet
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 1), ("test_charger_v2", 0)],
    indirect=["charger"],
)
async def test_get_gfi_trip_count(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.gfi_trip_count
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 246), ("test_charger_v2", 8751)],
    indirect=["charger"],
)
async def test_get_charge_time_elapsed(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.charge_time_elapsed
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", -61), ("test_charger_v2", -56)],
    indirect=["charger"],
)
async def test_get_wifi_signal(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.wifi_signal
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 32.2), ("test_charger_v2", 0)],
    indirect=["charger"],
)
async def test_get_charging_current(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.charging_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 48), ("test_charger_v2", 25)],
    indirect=["charger"],
)
async def test_get_current_capacity(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.current_capacity
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 50.3), ("test_charger_v2", 34.0)],
    indirect=["charger"],
)
async def test_get_ambient_temperature(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.ambient_temperature
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 50.3), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_get_rtc_temperature(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.rtc_temperature
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", None), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_get_ir_temperature(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.ir_temperature
    assert status is None
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 56.0), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_get_esp_temperature(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.esp_temperature
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", None), ("test_charger_v2", "4.0.1")],
    indirect=["charger"],
)
async def test_get_protocol_version(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.protocol_version
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 6), ("test_charger_v2", 6)],
    indirect=["charger"],
)
async def test_get_min_amps(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.min_amps
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 48), ("test_charger_v2", 48)],
    indirect=["charger"],
)
async def test_get_max_amps(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.max_amps
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 0), ("test_charger_v2", 1)],
    indirect=["charger"],
)
async def test_get_diodet(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.diode_check_enabled
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", None), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_get_available_current(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.available_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", None), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_get_smoothed_available_current(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.smoothed_available_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", False), ("test_charger_v2", False)],
    indirect=["charger"],
)
async def test_get_manual_override(charger, expected):
    """Test v4 Status reply."""
    await charger.update()
    status = charger.manual_override
    assert status == expected
    await charger.ws_disconnect()


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
    setattr(content_error, "real_url", f"{TEST_URL_RAPI}")
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


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", "1234567890AB"), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_wifi_serial(charger, expected):
    """Test wifi_serial reply."""
    await charger.update()
    status = charger.wifi_serial
    assert status == expected
    await charger.ws_disconnect()


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
    value = {"msg": "OK"}
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


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", True), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_shaper_active(charger, expected):
    """Test shaper_active reply."""
    await charger.update()
    status = charger.shaper_active
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 2299), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_shaper_live_power(charger, expected):
    """Test shaper_live_power reply."""
    await charger.update()
    status = charger.shaper_live_power
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 4000), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_shaper_max_power(charger, expected):
    """Test shaper_max_power reply."""
    await charger.update()
    status = charger.shaper_max_power
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 75), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_vehicle_soc(charger, expected):
    """Test vehicle_soc reply."""
    await charger.update()
    status = charger.vehicle_soc
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 468), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_vehicle_range(charger, expected):
    """Test vehicle_range reply."""
    await charger.update()
    status = charger.vehicle_range
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected_seconds", [("test_charger", 18000), ("test_charger_v2", None)],
    indirect=["charger"],
)
@freeze_time("2026-01-09 12:00:00+00:00")
async def test_vehicle_eta(charger, expected_seconds):
    """Test vehicle_eta reply."""
    await charger.update()

    result = charger.vehicle_eta

    if expected_seconds is not None:
        # Calculate what the expected datetime should be based on our frozen time
        expected_datetime = datetime(
            2026, 1, 9, 12, 0, 0, tzinfo=timezone.utc
        ) + timedelta(seconds=expected_seconds)
        assert result == expected_datetime
    else:
        assert result is None

    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", 48), ("test_charger_v2", 25)],
    indirect=["charger"],
)
async def test_max_current_soft(charger, expected):
    """Test max_current_soft reply."""
    await charger.update()
    status = charger.max_current_soft
    assert status == expected
    await charger.ws_disconnect()


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

    with pytest.raises(ValueError):
        with caplog.at_level(logging.DEBUG):
            await test_charger.set_override("invalid")
            assert "Invalid override state: invalid" in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.update()
            status = await test_charger_v2.set_override("active")
            assert "Feature not supported for older firmware." in caplog.text

            await test_charger_unknown_semver.update()
            status = await test_charger_unknown_semver.set_override("active")
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


async def test_version_check(test_charger_new, mock_aioclient, caplog):
    """Test version check function."""
    await test_charger_new.update()

    result = test_charger_new._version_check("4.0.0")
    assert result

    result = test_charger_new._version_check("4.0.0", "4.1.7")
    assert not result


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
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnknownError):
            await test_charger.set_charge_mode("fast")
            assert "Problem issuing command: error" in caplog.text

    value = {"msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with pytest.raises(ValueError):
        await test_charger.set_charge_mode("test")
    await test_charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger", "fast"), ("test_charger_v2", "fast")],
    indirect=["charger"],
)
async def test_charge_mode(charger, expected):
    """Test vehicle_range reply."""
    await charger.update()
    status = charger.charge_mode
    assert status == expected
    await charger.ws_disconnect()


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
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnknownError):
            await test_charger.set_service_level(1)
            assert "Problem issuing command: error" in caplog.text

    value = {"msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with pytest.raises(ValueError):
        await test_charger.set_service_level("A")
    await test_charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger_new", 48), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_max_current(charger, expected):
    """Test max_current reply."""
    await charger.update()
    status = charger.max_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger_new", 0), ("test_charger_v2", 0)],
    indirect=["charger"],
)
async def test_emoncms_connected(charger, expected):
    """Test emoncms_connected reply."""
    await charger.update()
    status = charger.emoncms_connected
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger_new", 0), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_ocpp_connected(charger, expected):
    """Test ocpp_connected reply."""
    await charger.update()
    status = charger.ocpp_connected
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger_new", 1208725), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_uptime(charger, expected):
    """Test uptime reply."""
    await charger.update()
    status = charger.uptime
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "charger, expected", [("test_charger_new", 167436), ("test_charger_v2", None)],
    indirect=["charger"],
)
async def test_freeram(charger, expected):
    """Test freeram reply."""
    await charger.update()
    status = charger.freeram
    assert status == expected
    await charger.ws_disconnect()


