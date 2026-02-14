"""Library tests."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import aiohttp
import pytest
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from aiohttp.client_reqrep import ConnectionKey
from awesomeversion import AwesomeVersion
from awesomeversion.exceptions import AwesomeVersionCompareException
from freezegun import freeze_time

import openevsehttp.__main__ as main
from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import (
    AlreadyListening,
    AuthenticationError,
    InvalidType,
    MissingMethod,
    MissingSerial,
    ParseJSONError,
    UnknownError,
    UnsupportedFeature,
)
from openevsehttp.websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STOPPED,
    OpenEVSEWebsocket,
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
    "fixture, expected",
    [("test_charger", "sleeping"), ("test_charger_v2", "not connected")],
)
async def test_get_status(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.status
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "Datanode-IoT"), ("test_charger_v2", "nsavanup_IoT")],
)
async def test_get_ssid(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_ssid
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "7.1.3"), ("test_charger_v2", "5.0.1")]
)
async def test_get_firmware(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.openevse_firmware
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "openevse-7b2c"), ("test_charger_v2", "openevse")],
)
async def test_get_hostname(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.hostname
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_ammeter_offset(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    await charger.ws_disconnect()
    status = charger.ammeter_offset
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 220), ("test_charger_v2", 220)]
)
async def test_get_ammeter_scale_factor(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
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
    "fixture, expected", [("test_charger", 2), ("test_charger_v2", 2)]
)
async def test_get_service_level(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.service_level
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", "4.1.2"),
        ("test_charger_v2", "2.9.1"),
        ("test_charger_dev", "4.1.5"),
        ("test_charger_broken_semver", "master_abcd123"),
    ],
)
async def test_get_wifi_firmware(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_firmware
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "192.168.21.10"), ("test_charger_v2", "192.168.1.67")],
)
async def test_get_ip_address(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ip_address
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 240), ("test_charger_v2", 240)]
)
async def test_get_charging_voltage(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_voltage
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "STA"), ("test_charger_v2", "STA")]
)
async def test_get_mode(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.mode
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_using_ethernet(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.using_ethernet
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_stuck_relay_trip_count(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.stuck_relay_trip_count
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_no_gnd_trip_count(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.no_gnd_trip_count
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 1), ("test_charger_v2", 0)]
)
async def test_get_gfi_trip_count(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.gfi_trip_count
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 246), ("test_charger_v2", 8751)]
)
async def test_get_charge_time_elapsed(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charge_time_elapsed
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", -61), ("test_charger_v2", -56)]
)
async def test_get_wifi_signal(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_signal
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 32.2), ("test_charger_v2", 0)]
)
async def test_get_charging_current(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 25)]
)
async def test_get_current_capacity(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.current_capacity
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", 64582),
        ("test_charger_v2", 1585443),
        ("test_charger_new", 20127.22817),
    ],
)
async def test_get_usage_total(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.usage_total
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 50.3), ("test_charger_v2", 34.0)]
)
async def test_get_ambient_temperature(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ambient_temperature
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 50.3), ("test_charger_v2", None)]
)
async def test_get_rtc_temperature(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.rtc_temperature
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", None)]
)
async def test_get_ir_temperature(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ir_temperature
    assert status is None
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 56.0), ("test_charger_v2", None)]
)
async def test_get_esp_temperature(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.esp_temperature
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected_str",
    [("test_charger", "2021-08-10T23:00:11Z"), ("test_charger_v2", None)],
)
async def test_get_time(fixture, expected_str, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()

    result = charger.time

    if expected_str:
        expected_dt = datetime(2021, 8, 10, 23, 0, 11, tzinfo=timezone.utc)
        assert result == expected_dt
        assert isinstance(result, datetime)
    else:
        assert result is None

    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "bad_value",
    [
        "not-a-timestamp",
        123456789,
        True,
        {"some": "dict"},
    ],
)
async def test_time_parsing_errors(test_charger, bad_value):
    """Test that ValueError and AttributeError are caught and return None."""
    test_charger._status["time"] = bad_value
    result = test_charger.time
    assert result is None


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", 275.71),
        ("test_charger_v2", 7003.41),
        ("test_charger_new", 0),
    ],
)
async def test_get_usage_session(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.usage_session
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", "4.0.1")]
)
async def test_get_protocol_version(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.protocol_version
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 6), ("test_charger_v2", 6)]
)
async def test_get_min_amps(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.min_amps
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 48)]
)
async def test_get_max_amps(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.max_amps
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_ota_update(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ota_update
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize("fixture, expected", [("test_charger", 1)])
async def test_get_vehicle(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vehicle
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "sleeping"), ("test_charger_v2", "not connected")],
)
async def test_get_state(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.state
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_tempt(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.temp_check_enabled
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 1)]
)
async def test_get_diodet(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.diode_check_enabled
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_ventt(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vent_required_enabled
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_groundt(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ground_check_enabled
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_relayt(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.stuck_relay_check_enabled
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_charge_rate(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charge_rate
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", None)]
)
async def test_get_available_current(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.available_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", None)]
)
async def test_get_smoothed_available_current(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.smoothed_available_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", True), ("test_charger_v2", False), ("test_charger_new", False)],
)
async def test_get_divert_active(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.divert_active
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_manual_override(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
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
    "fixture, expected", [("test_charger", "1234567890AB"), ("test_charger_v2", None)]
)
async def test_wifi_serial(fixture, expected, request):
    """Test wifi_serial reply."""
    charger = request.getfixturevalue(fixture)
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
    "fixture, expected",
    [("test_charger", 7728), ("test_charger_v2", 0), ("test_charger_broken", None)],
)
async def test_get_charging_power(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_power
    assert status == expected
    await charger.ws_disconnect()


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
    await test_charger_v2.update()
    await test_charger_v2.divert_mode()

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    await test_charger_broken.update()
    test_charger_broken._config["version"] = "4.1.8"
    with pytest.raises(UnsupportedFeature):
        await test_charger_broken.divert_mode()

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    await test_charger_unknown_semver.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_unknown_semver.divert_mode()
            assert "Non-semver firmware version detected." in caplog.text


async def test_test_and_get(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test v4 Status reply"""
    data = await test_charger.test_and_get()
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )
    assert data["serial"] == "1234567890AB"
    assert data["model"] == "unknown"

    with pytest.raises(MissingSerial):
        with caplog.at_level(logging.DEBUG):
            data = await test_charger_v2.test_and_get()
    assert "Older firmware detected, missing serial." in caplog.text


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
    """Test v4 Status reply"""
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
            ConnectionKey("localhost", 80, False, None, None, None, None),
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


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", True), ("test_charger_v2", None)]
)
async def test_shaper_active(fixture, expected, request):
    """Test shaper_active reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.shaper_active
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 2299), ("test_charger_v2", None)]
)
async def test_shaper_live_power(fixture, expected, request):
    """Test shaper_live_power reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.shaper_live_power
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", 21), ("test_charger_v2", None), ("test_charger_broken", 48)],
)
async def test_shaper_current_power(fixture, expected, request):
    """Test shaper_available_current reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.shaper_available_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 4000), ("test_charger_v2", None)]
)
async def test_shaper_max_power(fixture, expected, request):
    """Test shaper_max_power reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.shaper_max_power
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 75), ("test_charger_v2", None)]
)
async def test_vehicle_soc(fixture, expected, request):
    """Test vehicle_soc reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vehicle_soc
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 468), ("test_charger_v2", None)]
)
async def test_vehicle_range(fixture, expected, request):
    """Test vehicle_range reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vehicle_range
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected_seconds", [("test_charger", 18000), ("test_charger_v2", None)]
)
@freeze_time("2026-01-09 12:00:00+00:00")
async def test_vehicle_eta(fixture, expected_seconds, request):
    """Test vehicle_eta reply."""
    charger = request.getfixturevalue(fixture)
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
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 25)]
)
async def test_max_current_soft(fixture, expected, request):
    """Test max_current_soft reply."""
    charger = request.getfixturevalue(fixture)
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
    "fixture, expected", [("test_charger", "fast"), ("test_charger_v2", "fast")]
)
async def test_charge_mode(fixture, expected, request):
    """Test vehicle_range reply."""
    charger = request.getfixturevalue(fixture)
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
    "fixture, expected",
    [("test_charger", None), ("test_charger_v2", None), ("test_charger_new", False)],
)
async def test_get_has_limit(fixture, expected, request):
    """Test has_limit reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.has_limit
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", None), ("test_charger_v2", None), ("test_charger_new", 0)],
)
async def test_get_total_day(fixture, expected, request):
    """Test total_day reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.total_day
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", None),
        ("test_charger_v2", None),
        ("test_charger_new", 1.567628635),
    ],
)
async def test_get_total_week(fixture, expected, request):
    """Test total_week reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.total_week
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", None),
        ("test_charger_v2", None),
        ("test_charger_new", 37.21857071),
    ],
)
async def test_get_total_month(fixture, expected, request):
    """Test total_month reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.total_month
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", None),
        ("test_charger_v2", None),
        ("test_charger_new", 2155.219982),
    ],
)
async def test_get_total_year(fixture, expected, request):
    """Test total_year reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.total_year
    assert status == expected
    await charger.ws_disconnect()


async def test_websocket_functions(test_charger, mock_aioclient, caplog):
    """Test v4 Status reply."""
    mock_aioclient.get(
        TEST_URL_WS,
        status=200,
        body=load_fixture("websocket.json"),
    )
    await test_charger.update()
    test_charger.ws_start()
    await test_charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", 254), ("test_charger_v2", 1)],
)
async def test_get_state_raw(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.state_raw
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", True),
        ("test_charger_v2", False),
        ("test_charger_broken", False),
    ],
)
async def test_get_mqtt_connected(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.mqtt_connected
    assert status == expected
    await charger.ws_disconnect()


async def test_self_production(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test self_production function."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"grid_ie": 3000, "solar": 1000}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.self_production(-3000, 1000, True, 210)
        assert (
            "Posting self-production: {'grid_ie': 3000, 'voltage': 210}" in caplog.text
        )
        assert (
            "Self-production response: {'grid_ie': 3000, 'solar': 1000}" in caplog.text
        )

        await test_charger.self_production(None, 1000)
        assert "Posting self-production: {'solar': 1000}" in caplog.text

        await test_charger.self_production(None, None)
        assert "No sensor data to send to device." in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.self_production(-3000, 1000)
            assert "Feature not supported for older firmware." in caplog.text
        await test_charger.ws_disconnect()


async def test_soc(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test soc function."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"battery_level": 85, "battery_range": 230, "time_to_full_charge": 1590}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.soc(85, 230, 1590)
        assert (
            "Posting SOC data: {'battery_level': 85, 'battery_range': 230, 'time_to_full_charge': 1590}"
            in caplog.text
        )
        assert (
            "SOC response: {'battery_level': 85, 'battery_range': 230, 'time_to_full_charge': 1590}"
            in caplog.text
        )

        await test_charger.soc(voltage=220)
        assert "Posting SOC data: {'voltage': 220}" in caplog.text

        await test_charger.soc(None)
        assert "No SOC data to send to device." in caplog.text
        await test_charger.ws_disconnect()

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.soc(50, 90, 3100)
            assert "Feature not supported for older firmware." in caplog.text
        await test_charger_v2.ws_disconnect()


async def test_set_limit(
    test_charger_modified_ver, test_charger, mock_aioclient, caplog
):
    """Test set limit."""
    await test_charger_modified_ver.update()
    mock_aioclient.get(
        TEST_URL_LIMIT,
        status=200,
        body='{"type": "energy", "value": 10}',
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL_LIMIT,
        status=200,
        body='{"msg": "OK"}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.set_limit("energy", 15, True)
        assert (
            "Limit data: {'type': 'energy', 'value': 15, 'release': True}"
            in caplog.text
        )
        assert "Setting limit config on http://openevse.test.tld/limit" in caplog.text

    with pytest.raises(InvalidType):
        await test_charger_modified_ver.set_limit("invalid", 15)

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger.set_limit("energy", 15)
            assert "Feature not supported for older firmware." in caplog.text


async def test_get_limit(
    test_charger_modified_ver, test_charger, mock_aioclient, caplog
):
    """Test get limit."""
    await test_charger_modified_ver.update()
    mock_aioclient.get(
        TEST_URL_LIMIT,
        status=200,
        body='{"type": "energy", "value": 10}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger_modified_ver.get_limit()
        assert response == {"type": "energy", "value": 10}
        assert "Getting limit config on http://openevse.test.tld/limit" in caplog.text

    mock_aioclient.get(
        TEST_URL_LIMIT,
        status=404,
        body='{"msg": "No limit"}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger_modified_ver.get_limit()
        assert response == {"msg": "No limit"}

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger.get_limit()
            assert "Feature not supported for older firmware." in caplog.text


async def test_clear_limit(
    test_charger_modified_ver, test_charger, mock_aioclient, caplog
):
    """Test clear limit."""
    await test_charger_modified_ver.update()
    mock_aioclient.delete(
        TEST_URL_LIMIT,
        status=200,
        body='{"msg": "Deleted"}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger_modified_ver.clear_limit()
        assert response == {"msg": "Deleted"}
        assert "Clearing limit config on http://openevse.test.tld/limit" in caplog.text

    mock_aioclient.delete(
        TEST_URL_LIMIT,
        status=404,
        body='{"msg": "No limit to clear"}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger_modified_ver.clear_limit()
        assert response == {"msg": "No limit to clear"}

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger.clear_limit()
            assert "Feature not supported for older firmware." in caplog.text


async def test_voltage(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test voltage function."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"voltage": 210}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.grid_voltage(210)
        assert "Posting voltage: {'voltage': 210}" in caplog.text
        assert "Voltage posting response: {'voltage': 210}" in caplog.text

        await test_charger.grid_voltage(None)
        assert "No sensor data to send to device." in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.grid_voltage(210)
            assert "Feature not supported for older firmware." in caplog.text


async def test_list_claims(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test list_claims function."""
    await test_charger.update()
    mock_aioclient.get(
        TEST_URL_CLAIMS,
        status=200,
        body='[{"client":65540,"priority":10,"state":"disabled","auto_release":false}]',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.list_claims()
        assert f"Getting claims on {TEST_URL_CLAIMS}" in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.list_claims()
            assert "Feature not supported for older firmware." in caplog.text


async def test_release_claim(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test release_claim function."""
    await test_charger.update()
    mock_aioclient.delete(
        f"{TEST_URL_CLAIMS}/20",
        status=200,
        body='[{"msg":"done"}]',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.release_claim()
        assert f"Releasing claim on {TEST_URL_CLAIMS}/20" in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.release_claim()
            assert "Feature not supported for older firmware." in caplog.text


async def test_make_claim(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test make_claim function."""
    await test_charger.update()
    mock_aioclient.post(
        f"{TEST_URL_CLAIMS}/20",
        status=200,
        body='[{"msg":"done"}]',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.make_claim(
            state="disabled", charge_current=20, max_current=20
        )
        assert (
            "Claim data: {'auto_release': True, 'state': 'disabled', 'charge_current': 20, 'max_current': 20}"
            in caplog.text
        )
        assert f"Setting up claim on {TEST_URL_CLAIMS}/20" in caplog.text

    with pytest.raises(ValueError):
        with caplog.at_level(logging.DEBUG):
            await test_charger.make_claim("invalid")
            assert "Invalid claim state: invalid" in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.make_claim()
            assert "Feature not supported for older firmware." in caplog.text


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", 48), ("test_charger_v2", None)]
)
async def test_max_current(fixture, expected, request):
    """Test max_current reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.max_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", 0), ("test_charger_v2", 0)]
)
async def test_emoncms_connected(fixture, expected, request):
    """Test emoncms_connected reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.emoncms_connected
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", 0), ("test_charger_v2", None)]
)
async def test_ocpp_connected(fixture, expected, request):
    """Test ocpp_connected reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ocpp_connected
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", 1208725), ("test_charger_v2", None)]
)
async def test_uptime(fixture, expected, request):
    """Test uptime reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.uptime
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", 167436), ("test_charger_v2", None)]
)
async def test_freeram(fixture, expected, request):
    """Test freeram reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.freeram
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger_new", {"gfcicount": 1, "nogndcount": 0, "stuckcount": 0}),
        ("test_charger_v2", {"gfcicount": 0, "nogndcount": 0, "stuckcount": 0}),
    ],
)
async def test_checks_count(fixture, expected, request):
    """Test checks_count reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.checks_count
    assert status == expected
    await charger.ws_disconnect()


async def test_led_brightness(test_charger_new, test_charger_v2, caplog):
    """Test led_brightness reply."""
    await test_charger_new.update()
    status = test_charger_new.led_brightness
    assert status == 125

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            status = await test_charger_v2.led_brightness
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

    value = await test_charger.async_charge_current
    assert value == 28

    mock_aioclient.get(
        TEST_URL_CLAIMS_TARGET,
        status=200,
        body='{"properties":{"state":"disabled","max_current":23,"auto_release":false},"claims":{"state":65540,"charge_current":65537,"max_current":65548}}',
        repeat=False,
    )

    value = await test_charger.async_charge_current
    assert value == 48
    await test_charger.ws_disconnect()

    await test_charger_v2.update()
    value = await test_charger_v2.async_charge_current
    assert value == 25
    await test_charger_v2.ws_disconnect()


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
        status = await test_charger.async_override_state
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
        status = await test_charger.async_override_state
        assert status == "disabled"

    value = {}
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        status = await test_charger.async_override_state
        assert status == "auto"

    with caplog.at_level(logging.DEBUG):
        await test_charger_v2.update()
        await test_charger_v2.async_override_state
        assert "Override state unavailable on older firmware." in caplog.text


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", False),
        ("test_charger_v2", False),
        ("test_charger_broken", False),
        ("test_charger_new", True),
    ],
)
async def test_get_shaper_updated(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.shaper_updated
    assert status == expected
    await charger.ws_disconnect()


async def test_get_status_error(test_charger_timeout, caplog):
    """Test v4 Status reply."""
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(TimeoutError):
            await test_charger_timeout.update()
        assert test_charger_timeout.websocket is None
        assert not test_charger_timeout._ws_listening
    assert "Updating data from http://openevse.test.tld/status" in caplog.text
    assert "Status update:" not in caplog.text
    assert "Config update:" not in caplog.text


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", "eco"),
        ("test_charger_v2", "fast"),
        ("test_charger_broken", "eco"),
        ("test_charger_new", "fast"),
    ],
)
async def test_divertmode(fixture, expected, request):
    """Test divertmode property."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.divertmode
    assert status == expected
    await charger.ws_disconnect()


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


async def test_main_auth_instantiation():
    """Test OpenEVSE auth instantiation."""
    charger = OpenEVSE(SERVER_URL, user="user", pwd="password")

    # Setup mock session to be an async context manager
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Setup mock response context to be an async context manager
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text.return_value = "{}"

    mock_request_ctx = MagicMock()
    mock_request_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_request_ctx.__aexit__ = AsyncMock(return_value=None)

    # Ensure session.get() returns the request context
    mock_session.get.return_value = mock_request_ctx

    with (
        patch("aiohttp.ClientSession", return_value=mock_session),
        patch("aiohttp.BasicAuth") as mock_basic_auth,
    ):
        await charger.update()

        # Verify BasicAuth was instantiated
        # Note: process_request is called multiple times in update(), so we check if called at least once
        mock_basic_auth.assert_called_with("user", "password")


async def test_main_sync_callback():
    """Test synchronous callback in _update_status."""
    charger = OpenEVSE(SERVER_URL)
    sync_callback = MagicMock()
    charger.callback = sync_callback

    # Manually trigger update status
    await charger._update_status("data", {"key": "value"}, None)

    sync_callback.assert_called_once()


async def test_send_command_msg_fallback():
    """Test send_command return logic fallback."""
    charger = OpenEVSE(SERVER_URL)

    # Mock response with 'msg' but no 'ret'
    with patch.object(charger, "process_request", return_value={"msg": "ErrorMsg"}):
        cmd, ret = await charger.send_command("$ST")
        assert cmd is False
        assert ret == "ErrorMsg"


async def test_send_command_empty_fallback():
    """Test send_command empty fallback."""
    charger = OpenEVSE(SERVER_URL)

    # Mock response with neither 'msg' nor 'ret'
    with patch.object(charger, "process_request", return_value={}):
        cmd, ret = await charger.send_command("$ST")
        assert cmd is False
        assert ret == ""


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("test_charger", UnsupportedFeature),
        ("test_charger_v2", UnsupportedFeature),
        ("test_charger_broken", UnsupportedFeature),
        ("test_charger_new", 4500),
    ],
)
async def test_power(fixture, expected, request):
    """Test current_power property."""
    charger = request.getfixturevalue(fixture)
    await charger.update()

    # If we expect an exception (UnsupportedFeature), we must use pytest.raises
    if expected is UnsupportedFeature:
        with pytest.raises(UnsupportedFeature):
            _ = charger.current_power
    else:
        # Otherwise, we check the returned value
        assert charger.current_power == expected

    await charger.ws_disconnect()


# Additional coverage tests for error handling and edge cases


async def test_process_request_missing_method():
    """Test process_request raises error when method is None."""

    charger = OpenEVSE(SERVER_URL)

    with pytest.raises(MissingMethod):
        await charger.process_request(TEST_URL_STATUS, method=None)


async def test_process_request_unicode_decode_error(mock_aioclient):
    """Test process_request handles UnicodeDecodeError."""
    # Create a mock response that raises UnicodeDecodeError on text()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(
        side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "")
    )
    mock_response.read = AsyncMock(return_value=b'{"status": "ok"}')

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body='{"status": "ok"}',
    )

    # Patch the session.get to return our mock response
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        charger = OpenEVSE(SERVER_URL)
        result = await charger.process_request(TEST_URL_STATUS, method="get")

        assert result == {"status": "ok"}


async def test_process_request_non_json_response(mock_aioclient):
    """Test process_request handles non-JSON response."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body="Not JSON",
    )

    charger = OpenEVSE(SERVER_URL)
    result = await charger.process_request(TEST_URL_STATUS, method="get")

    # Should return the string as-is
    assert result == "Not JSON"


async def test_process_request_400_error_with_msg(mock_aioclient):
    """Test process_request handles 400 error with msg field."""

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=400,
        body='{"msg": "Bad request"}',
    )

    charger = OpenEVSE(SERVER_URL)

    with pytest.raises(ParseJSONError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_400_error_with_error_field(mock_aioclient):
    """Test process_request handles 400 error with error field."""

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=400,
        body='{"error": "Invalid input"}',
    )

    charger = OpenEVSE(SERVER_URL)

    with pytest.raises(ParseJSONError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_401_error(mock_aioclient):
    """Test process_request handles 401 authentication error."""

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=401,
        body='{"error": "Unauthorized"}',
    )

    charger = OpenEVSE(SERVER_URL)

    with pytest.raises(AuthenticationError):
        await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_404_error(mock_aioclient):
    """Test process_request handles 404 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=404,
        body='{"error": "Not found"}',
    )

    charger = OpenEVSE(SERVER_URL)
    # Should not raise, just log warning
    result = await charger.process_request(TEST_URL_STATUS, method="get")
    assert result == {"error": "Not found"}


async def test_process_request_405_error(mock_aioclient):
    """Test process_request handles 405 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=405,
        body='{"error": "Method not allowed"}',
    )

    charger = OpenEVSE(SERVER_URL)
    # Should not raise, just log warning
    result = await charger.process_request(TEST_URL_STATUS, method="get")
    assert result == {"error": "Method not allowed"}


async def test_process_request_500_error(mock_aioclient):
    """Test process_request handles 500 error."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=500,
        body='{"error": "Internal server error"}',
    )

    charger = OpenEVSE(SERVER_URL)
    # Should not raise, just log warning
    result = await charger.process_request(TEST_URL_STATUS, method="get")
    assert result == {"error": "Internal server error"}


async def test_process_request_timeout_error():
    """Test process_request handles TimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = TimeoutError("Connection timeout")

        charger = OpenEVSE(SERVER_URL)

        with pytest.raises(TimeoutError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_server_timeout_error():
    """Test process_request handles ServerTimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = ServerTimeoutError("Server timeout")

        charger = OpenEVSE(SERVER_URL)

        with pytest.raises(ServerTimeoutError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_content_type_error():
    """Test process_request handles ContentTypeError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        error = ContentTypeError(
            request_info=MagicMock(),
            history=(),
            message="Invalid content type",
        )
        mock_get.side_effect = error

        charger = OpenEVSE(SERVER_URL)

        with pytest.raises(ContentTypeError):
            await charger.process_request(TEST_URL_STATUS, method="get")


async def test_process_request_post_with_config_version(mock_aioclient):
    """Test process_request calls update when posting config_version."""
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"config_version": "1.0"}',
    )
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

    charger = OpenEVSE(SERVER_URL)

    # This should trigger update() because of config_version in response
    result = await charger.process_request(TEST_URL_CONFIG, method="post", data={})

    assert "config_version" in result
    # Verify update was called by checking if status was set
    assert charger._status is not None


async def test_send_command_no_ret_with_msg(mock_aioclient):
    """Test send_command when response has msg but no ret."""
    mock_aioclient.post(
        "http://openevse.test.tld/r",
        status=200,
        body='{"msg": "Command failed"}',
    )

    charger = OpenEVSE(SERVER_URL)
    result = await charger.send_command("test_command")

    assert result == (False, "Command failed")


async def test_send_command_no_ret_no_msg(mock_aioclient):
    """Test send_command when response has neither ret nor msg."""
    mock_aioclient.post(
        "http://openevse.test.tld/r",
        status=200,
        body='{"error": "Unknown"}',
    )

    charger = OpenEVSE(SERVER_URL)
    result = await charger.send_command("test_command")

    assert result == (False, "")


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


async def test_property_getters_with_missing_data(mock_aioclient):
    """Test property getters when data is missing."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body="{}",  # Empty status
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body="{}",  # Empty config
    )

    charger = OpenEVSE(SERVER_URL)
    await charger.update()

    # Test various properties that should handle missing data
    # String/numeric properties return None
    assert charger.hostname is None
    assert charger.ammeter_offset is None
    assert charger.ammeter_scale_factor is None
    assert charger.service_level is None

    # Boolean properties return False when data is missing
    assert charger.temp_check_enabled is False
    assert charger.diode_check_enabled is False
    assert charger.vent_required_enabled is False
    assert charger.ground_check_enabled is False
    assert charger.stuck_relay_check_enabled is False


async def test_external_session_with_error_handling(mock_aioclient):
    """Test external session handles errors properly."""

    mock_aioclient.get(
        TEST_URL_STATUS,
        status=401,
        body='{"error": "Unauthorized"}',
    )

    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)

        with pytest.raises(AuthenticationError):
            await charger.process_request(TEST_URL_STATUS, method="get")

        # Session should still be open
        assert not session.closed


async def test_external_session_unicode_decode_error():
    """Test external session handles UnicodeDecodeError."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(
        side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "")
    )
    mock_response.read = AsyncMock(return_value=b'{"status": "ok"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == {"status": "ok"}


async def test_external_session_non_json_response():
    """Test external session handles non-JSON response."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="Not JSON")

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == "Not JSON"


async def test_external_session_400_error_with_msg():
    """Test external session handles 400 error with msg field."""
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"msg": "Bad request"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(ParseJSONError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_400_error_with_error_field():
    """Test external session handles 400 error with error field."""
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"error": "Invalid input"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(ParseJSONError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_401_error():
    """Test external session handles 401 authentication error."""
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.text = AsyncMock(return_value='{"error": "Unauthorized"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(AuthenticationError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_404_error():
    """Test external session handles 404 error."""
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value='{"error": "Not found"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == {"error": "Not found"}


async def test_external_session_405_error():
    """Test external session handles 405 error."""
    mock_response = AsyncMock()
    mock_response.status = 405
    mock_response.text = AsyncMock(return_value='{"error": "Method not allowed"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == {"error": "Method not allowed"}


async def test_external_session_500_error():
    """Test external session handles 500 error."""
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value='{"error": "Internal server error"}')

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)
            result = await charger.process_request(TEST_URL_STATUS, method="get")

            assert result == {"error": "Internal server error"}


async def test_external_session_post_with_config_version(mock_aioclient):
    """Test external session with POST that triggers update."""
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body='{"config_version": "1.0"}',
    )
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

    async with aiohttp.ClientSession() as session:
        charger = OpenEVSE(SERVER_URL, session=session)
        result = await charger.process_request(TEST_URL_CONFIG, method="post", data={})

        assert "config_version" in result
        assert charger._status is not None


async def test_external_session_timeout_error():
    """Test external session handles TimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = TimeoutError("Connection timeout")

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(TimeoutError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_server_timeout_error():
    """Test external session handles ServerTimeoutError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = ServerTimeoutError("Server timeout")

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(ServerTimeoutError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_external_session_content_type_error():
    """Test external session handles ContentTypeError."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        error = ContentTypeError(
            request_info=MagicMock(),
            history=(),
            message="Invalid content type",
        )
        mock_get.side_effect = error

        async with aiohttp.ClientSession() as session:
            charger = OpenEVSE(SERVER_URL, session=session)

            with pytest.raises(ContentTypeError):
                await charger.process_request(TEST_URL_STATUS, method="get")


async def test_identify_with_buildenv(mock_aioclient):
    """Test test_and_get method (identify) with buildenv in response."""
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"wifi_serial": "123", "buildenv": "esp32"}',
    )
    charger = OpenEVSE(SERVER_URL)
    data = await charger.test_and_get()
    assert data["model"] == "esp32"


async def test_ws_start_already_listening():
    """Test ws_start raises AlreadyListening if already listening."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.state = "connected"
    charger._ws_listening = True

    with pytest.raises(AlreadyListening):
        charger.ws_start()


async def test_ws_start_reset_listening():
    """Test ws_start resets _ws_listening if websocket is not connected."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.state = "disconnected"
    charger._ws_listening = True

    with patch.object(charger, "_start_listening"):
        charger.ws_start()
        assert charger._ws_listening is False


async def test_start_listening_no_loop():
    """Test _start_listening when no running loop is found."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()

    with patch("asyncio.get_running_loop", side_effect=RuntimeError):
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            charger._start_listening()
            assert charger._loop == mock_loop


async def test_update_status_states():
    """Test _update_status with different websocket states."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.uri = "ws://test"

    # Test connected
    await charger._update_status(SIGNAL_CONNECTION_STATE, STATE_CONNECTED, None)
    assert charger._ws_listening is True

    # Test disconnected
    await charger._update_status(
        SIGNAL_CONNECTION_STATE, STATE_DISCONNECTED, "test error"
    )
    assert charger._ws_listening is False

    # Test stopped with error
    await charger._update_status(SIGNAL_CONNECTION_STATE, STATE_STOPPED, "fatal error")
    assert charger._ws_listening is False


async def test_update_status_data_triggers(mock_aioclient):
    """Test _update_status with data that triggers update and callback."""
    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body='{"version": "4.0.1"}',
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"hostname": "test"}',
    )

    charger = OpenEVSE(SERVER_URL)

    # Set a coroutine callback
    mock_callback = AsyncMock()
    charger.callback = mock_callback

    # "wh" should be popped to "watthour"
    # "config_version" is in UPDATE_TRIGGERS
    data = {"wh": 100, "config_version": 2}
    await charger._update_status("data", data, None)

    assert data["watthour"] == 100
    assert "wh" not in data
    assert charger._status["watthour"] == 100
    mock_callback.assert_called_once()

    # Test non-coroutine callback
    charger.callback = MagicMock()
    await charger._update_status("data", {"test": 1}, None)
    charger.callback.assert_called_once()


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


async def test_get_schedule(mock_aioclient):
    """Test get_schedule method."""
    mock_aioclient.post(
        "http://openevse.test.tld/schedule",
        status=200,
        body='{"sc": 1}',
    )
    charger = OpenEVSE(SERVER_URL)
    result = await charger.get_schedule()
    assert result == {"sc": 1}


async def test_repeat():
    """Test repeat helper."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    # Mock ws_state to stop after one iteration
    with patch(
        "openevsehttp.__main__.OpenEVSE.ws_state", new_callable=PropertyMock
    ) as mock_state:
        mock_state.side_effect = ["connected", "stopped"]

        mock_func = AsyncMock()
        with patch("asyncio.sleep", AsyncMock()):
            await charger.repeat(1, mock_func, "test")
            mock_func.assert_called_once_with("test")


async def test_ir_temperature():
    """Test ir_temperature property."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {"temp3": 250}
    assert charger.ir_temperature == 25.0


async def test_usage_session_none():
    """Test usage_session returns None when no data is present."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {}
    assert charger.usage_session is None


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
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"hostname": "test", "version": "4.0.1"}',
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
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "4.0.1"
    assert await charger.firmware_check() is None

    # ContentTypeError from github

    mock_aioclient.get(
        url, exception=ContentTypeError(MagicMock(), MagicMock(), message="test")
    )
    assert await charger.firmware_check() is None


async def test_websocket_pong():
    """Test websocket handles pong message."""

    callback = AsyncMock()
    async with aiohttp.ClientSession() as session:
        ws = OpenEVSEWebsocket(f"http://{SERVER_URL}", callback, session=session)

        mock_ws = AsyncMock()
        # Mock the async iterator of ws_client
        msg = MagicMock()
        msg.type = aiohttp.WSMsgType.TEXT
        msg.json.return_value = {"pong": 1}
        mock_ws.__aiter__.return_value = [msg]

        with patch.object(session, "ws_connect") as mock_ws_connect:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_ws
            mock_ws_connect.return_value = mock_context

            # Set state to stopped after one iteration to break the loop
            ws.state = "connected"

            async def side_effect(msgtype, data, error):
                if msgtype == SIGNAL_CONNECTION_STATE and data == STATE_STOPPED:
                    pass
                elif msgtype == "data" and "pong" in data:
                    ws.state = "stopped"

            callback.side_effect = side_effect

            await ws.running()
            assert ws._pong is not None


async def test_websocket_listen():
    """Test websocket listen calls running."""

    callback = AsyncMock()
    ws = OpenEVSEWebsocket(f"http://{SERVER_URL}", callback)

    with patch.object(ws, "running", AsyncMock()) as mock_running:
        # Break loop after first call
        ws.state = "starting"

        async def side_effect():
            ws.state = "stopped"

        mock_running.side_effect = side_effect

        await ws.listen()
        mock_running.assert_called_once()


async def test_websocket_stop_break():
    """Test websocket stops loop when state is stopped."""

    callback = AsyncMock()
    async with aiohttp.ClientSession() as session:
        ws = OpenEVSEWebsocket(f"http://{SERVER_URL}", callback, session=session)

        mock_ws = AsyncMock()
        msg = MagicMock()
        msg.type = aiohttp.WSMsgType.TEXT
        msg.json.return_value = {"test": 1}
        mock_ws.__aiter__.return_value = [msg, msg]

        with patch.object(session, "ws_connect") as mock_ws_connect:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_ws
            mock_ws_connect.return_value = mock_context

            ws.state = "connected"

            async def side_effect(msgtype, _data, _error):
                if msgtype == "data":
                    ws._state = "stopped"  # Direct set to avoid callback loop

            callback.side_effect = side_effect

            await ws.running()
            # Check that we received "data" once
            calls = [call for call in callback.call_args_list if call[0][0] == "data"]
            assert len(calls) == 1
