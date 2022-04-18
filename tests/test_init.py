import asyncio
import json
from unittest import mock

import logging
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

import pytest

import openevsehttp

pytestmark = pytest.mark.asyncio

TEST_URL_RAPI = "http://openevse.test.tld/r"
TEST_URL_OVERRIDE = "http://openevse.test.tld/override"
TEST_URL_CONFIG = "http://openevse.test.tld/config"


async def test_get_status_auth(test_charger_auth):
    """Test v4 Status reply"""
    await test_charger_auth.update()
    status = test_charger_auth.status
    assert status == "sleeping"


async def test_get_status_auth_err(test_charger_auth_err):
    """Test v4 Status reply"""
    with pytest.raises(openevsehttp.AuthenticationError):
        await test_charger_auth_err.update()
        assert test_charger_auth_err is None


async def test_send_command(test_charger, mock_aioclient):
    """Test v4 Status reply"""
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == ("OK", "$OK^20")


async def test_send_command_failed(test_charger, mock_aioclient):
    """Test v4 Status reply"""
    value = {"cmd": "OK", "ret": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == ("OK", "$NK^21")


async def test_send_command_missing(test_charger, mock_aioclient):
    """Test v4 Status reply"""
    value = {"cmd": "OK", "what": "$NK^21"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger.send_command("test")
    assert status == (False, "")


async def test_send_command_auth(test_charger_auth, mock_aioclient):
    """Test v4 Status reply"""
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=200,
        body=json.dumps(value),
    )
    status = await test_charger_auth.send_command("test")
    assert status == ("OK", "$OK^20")


async def test_send_command_parse_err(test_charger_auth, mock_aioclient):
    """Test v4 Status reply"""
    mock_aioclient.post(
        TEST_URL_RAPI, status=400, body='{"msg": "Could not parse JSON"}'
    )
    with pytest.raises(openevsehttp.ParseJSONError):
        status = await test_charger_auth.send_command("test")
        assert status is None


async def test_send_command_auth_err(test_charger_auth, mock_aioclient):
    """Test v4 Status reply"""
    mock_aioclient.post(
        TEST_URL_RAPI,
        status=401,
    )
    with pytest.raises(openevsehttp.AuthenticationError):
        status = await test_charger_auth.send_command("test")
        assert status is None


async def test_send_command_async_timeout(test_charger_auth, mock_aioclient, caplog):
    """Test v4 Status reply"""
    mock_aioclient.post(
        TEST_URL_RAPI,
        exception=TimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_auth.send_command("test")
    assert openevsehttp.ERROR_TIMEOUT in caplog.text


async def test_send_command_server_timeout(test_charger_auth, mock_aioclient, caplog):
    """Test v4 Status reply"""
    mock_aioclient.post(
        TEST_URL_RAPI,
        exception=ServerTimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_auth.send_command("test")
    assert f"{openevsehttp.ERROR_TIMEOUT}: {TEST_URL_RAPI}" in caplog.text


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "sleeping"), ("test_charger_v2", "not connected")],
)
async def test_get_status(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.status
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "Datanode-IoT"), ("test_charger_v2", "nsavanup_IoT")],
)
async def test_get_ssid(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_ssid
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "7.1.3"), ("test_charger_v2", "5.0.1")]
)
async def test_get_firmware(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.openevse_firmware
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "openevse-7b2c"), ("test_charger_v2", "openevse")],
)
async def test_get_hostname(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.hostname
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_ammeter_offset(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    charger.ws_disconnect()
    status = charger.ammeter_offset
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 220), ("test_charger_v2", 220)]
)
async def test_get_ammeter_scale_factor(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ammeter_scale_factor
    assert status == expected


# Checks don't seem to be working
# async def test_get_temp_check_enabled(fixture, expected, request):
#     """Test v4 Status reply"""
#     status = fixture, expected, request.temp_check_enabled
#     assert status


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 2), ("test_charger_v2", 2)]
)
async def test_get_service_level(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.service_level
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "4.1.2"), ("test_charger_v2", "2.9.1")]
)
async def test_get_wifi_firmware(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_firmware
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "192.168.21.10"), ("test_charger_v2", "192.168.1.67")],
)
async def test_get_ip_address(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ip_address
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 240), ("test_charger_v2", 240)]
)
async def test_get_charging_voltage(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_voltage
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "STA"), ("test_charger_v2", "STA")]
)
async def test_get_mode(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.mode
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_using_ethernet(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.using_ethernet
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_stuck_relay_trip_count(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.stuck_relay_trip_count
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_no_gnd_trip_count(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.no_gnd_trip_count
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 1), ("test_charger_v2", 0)]
)
async def test_get_gfi_trip_count(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.gfi_trip_count
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 246), ("test_charger_v2", 8751)]
)
async def test_get_charge_time_elapsed(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charge_time_elapsed
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", -61), ("test_charger_v2", -56)]
)
async def test_get_wifi_signal(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_signal
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 32.2), ("test_charger_v2", 0)]
)
async def test_get_charging_current(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_current
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 25)]
)
async def test_get_current_capacity(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.current_capacity
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 64582), ("test_charger_v2", 1585443)]
)
async def test_get_usage_total(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.usage_total
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 50.3), ("test_charger_v2", 34.0)]
)
async def test_get_ambient_temperature(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ambient_temperature
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 50.3), ("test_charger_v2", None)]
)
async def test_get_rtc_temperature(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.rtc_temperature
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", None)]
)
async def test_get_ir_temperature(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ir_temperature
    assert status is None


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 56.0), ("test_charger_v2", None)]
)
async def test_get_esp_temperature(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.esp_temperature
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "2021-08-10T23:00:11Z"), ("test_charger_v2", None)],
)
async def test_get_time(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.time
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 275.71), ("test_charger_v2", 7003.41)]
)
async def test_get_usage_session(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.usage_session
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "-"), ("test_charger_v2", "4.0.1")]
)
async def test_get_protocol_version(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.protocol_version
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 6), ("test_charger_v2", 6)]
)
async def test_get_min_amps(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.min_amps
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 48)]
)
async def test_get_max_amps(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.max_amps
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_ota_update(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ota_update
    assert status == expected


@pytest.mark.parametrize("fixture, expected", [("test_charger", 1)])
async def test_get_vehicle(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vehicle
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "sleeping"), ("test_charger_v2", "not connected")],
)
async def test_get_state(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.state
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_tempt(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.temp_check_enabled
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 1)]
)
async def test_get_diodet(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.diode_check_enabled
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_ventt(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vent_required_enabled
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_groundt(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ground_check_enabled
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_relayt(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.stuck_relay_check_enabled
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "eco"), ("test_charger_v2", "normal")]
)
async def test_get_divertmode(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.divertmode
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_charge_rate(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charge_rate
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_available_current(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    with pytest.raises(KeyError):
        status = charger.available_current
        # assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_smoothed_available_current(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    with pytest.raises(KeyError):
        status = charger.smoothed_available_current
        # assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_divert_active(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    with pytest.raises(KeyError):
        status = charger.divert_active
        # assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_manual_override(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    with pytest.raises(KeyError):
        status = charger.manual_override
        # assert status == expected


async def test_toggle_override(test_charger, mock_aioclient, caplog):
    """Test v4 Status reply"""
    await test_charger.update()
    mock_aioclient.patch(
        TEST_URL_OVERRIDE,
        status=200,
        body="OK",
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.toggle_override()
    assert "Toggling manual override http" in caplog.text


async def test_toggle_override_v2(test_charger_v2, mock_aioclient, caplog):
    """Test v4 Status reply"""
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
    """Test v4 Status reply"""
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
        await test_charger_v2.toggle_override()
    assert (
        "Toggle response: 0, message='Attempt to decode JSON with unexpected mimetype: text/html', url='http://openevse.test.tld/r'"
        in caplog.text
    )


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "1234567890AB"), ("test_charger_v2", None)]
)
async def test_wifi_serial(fixture, expected, request):
    """Test wifi_serial reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_serial
    assert status == expected


async def test_set_current(test_charger, mock_aioclient, caplog):
    """Test v4 Status reply"""
    await test_charger.update()
    value = {"msg": "done"}
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_current(12)
    assert "Setting max_current_soft to 12" in caplog.text


async def test_set_current_error(test_charger, mock_aioclient, caplog):
    """Test v4 Status reply"""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body="OK",
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError):
            await test_charger.set_current(60)
    assert "Invalid value for max_current_soft: 60" in caplog.text


async def test_set_current_v2(test_charger_v2, mock_aioclient, caplog):
    """Test v4 Status reply"""
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


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 7728), ("test_charger_v2", 0)]
)
async def test_get_charging_power(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_power
    assert status == expected
