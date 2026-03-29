"""Tests for OpenEVSE Client."""

import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from freezegun import freeze_time

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import (
    AlreadyListening,
    MissingSerial,
    UnknownError,
    UnsupportedFeature,
)
from openevsehttp.websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STOPPED,
)
from tests.common import load_fixture
from tests.const import (
    SERVER_URL,
    TEST_URL_CONFIG,
    TEST_URL_RESTART,
    TEST_URL_STATUS,
)

pytestmark = pytest.mark.asyncio


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
        "http://openevse.test.tld/override",
        status=200,
        body=json.dumps(value),
    )
    mock_aioclient.post(
        "http://openevse.test.tld/override",
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
        "http://openevse.test.tld/override",
        status=200,
        body=json.dumps(value),
        repeat=True,
    )
    mock_aioclient.post(
        "http://openevse.test.tld/override",
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError):
            await test_charger.set_current(60)
    assert "Invalid value for current limit: 60" in caplog.text

    await test_charger_broken.update()
    mock_aioclient.post(
        "http://openevse.test.tld/r",
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
        "http://openevse.test.tld/r",
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
        "http://openevse.test.tld/override",
        status=200,
        body=json.dumps(value),
    )
    mock_aioclient.post(
        "http://openevse.test.tld/override",
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
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_unknown_semver.divert_mode()
    assert "Non-semver firmware version detected." in caplog.text


async def test_test_and_get(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test v4 Status reply."""
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )
    data = await test_charger.test_and_get()
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
    assert "WiFi Restart response: restart gateway" in caplog.text


async def test_evse_restart(
    test_charger_v2, test_charger_modified_ver, mock_aioclient, caplog
):
    """Test EVSE module restart."""
    await test_charger_v2.update()
    value = {"cmd": "OK", "ret": "$OK^20"}
    mock_aioclient.post(
        "http://openevse.test.tld/r",
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_v2.restart_evse()
    assert "EVSE Restart response: $OK^20" in caplog.text
    assert "Restarting EVSE module via RAPI" in caplog.text

    await test_charger_modified_ver.update()
    mock_aioclient.post(
        TEST_URL_RESTART,
        status=200,
        body='{"msg": "restart evse"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.restart_evse()
    assert "Restarting EVSE module via HTTP" in caplog.text
    assert "EVSE Restart response: restart evse" in caplog.text


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


async def test_get_override_state(test_charger_new, mock_aioclient):
    """Test get_override_state reply."""
    await test_charger_new.update()
    mock_aioclient.get(
        "http://openevse.test.tld/override",
        status=200,
        body='{"state": "disabled"}',
    )
    status = await test_charger_new.get_override_state()
    assert status == "disabled"
    await test_charger_new.ws_disconnect()


async def test_current_power(test_charger_new, mock_aioclient):
    """Test current_power reply."""
    await test_charger_new.update()
    status = test_charger_new.current_power
    assert status == 4500
    await test_charger_new.ws_disconnect()


async def test_get_charge_current(test_charger_new, mock_aioclient):
    """Test get_charge_current reply."""
    await test_charger_new.update()
    mock_aioclient.get(
        "http://openevse.test.tld/claims/target",
        status=200,
        body='{"properties": {"charge_current": 10}}',
    )
    status = await test_charger_new.get_charge_current()
    assert status == 10
    await test_charger_new.ws_disconnect()


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
        await charger.ws_start()


async def test_ws_start_reset_listening():
    """Test ws_start resets _ws_listening if websocket is not connected."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()
    charger.websocket.state = "disconnected"
    charger._ws_listening = True

    with patch.object(charger, "_start_listening", AsyncMock()):
        await charger.ws_start()
        assert charger._ws_listening is False


async def test_start_listening_no_loop():
    """Test _start_listening when no running loop is found."""
    charger = OpenEVSE(SERVER_URL)
    charger.websocket = MagicMock()

    with patch("asyncio.get_running_loop", side_effect=RuntimeError):
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            await charger._start_listening()
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
    mock_callback = MagicMock()
    # Mocking is_coroutine_function to return False so we can use a simple MagicMock
    with patch.object(charger, "is_coroutine_function", return_value=False):
        charger.callback = mock_callback

        data = {"wh": 100, "config_version": 2}
        await charger._update_status("data", data, None)

        assert data["watthour"] == 100
        assert "wh" not in data
        assert charger._status["watthour"] == 100
        mock_callback.assert_called_once()


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
        "openevsehttp.client.OpenEVSE.ws_state", new_callable=PropertyMock
    ) as mock_state:
        mock_state.side_effect = ["connected", "stopped"]

        mock_func = AsyncMock()
        with patch("asyncio.sleep", AsyncMock()):
            await charger.repeat(1, mock_func, "test")
            mock_func.assert_called_once_with("test")


async def test_usage_session_none():
    """Test usage_session returns None when no data is present."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {}
    assert charger.usage_session is None


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
    assert "Problem issuing command. Response: {'msg': 'error'}" in caplog.text

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
    assert "Set service level to: 1" in caplog.text


@pytest.mark.asyncio
async def test_ws_disconnect_extra():
    """Test ws_disconnect calls close."""
    charger = OpenEVSE(SERVER_URL)
    ws_mock = MagicMock()
    ws_mock.close = AsyncMock()
    charger.websocket = ws_mock
    # Mock repeat to avoid unawaited coroutine warning
    with patch.object(charger, "repeat", AsyncMock()):
        await charger.ws_disconnect()
    ws_mock.close.assert_called_once()
    assert charger.websocket is None
    assert charger._ws_listening is False


async def test_is_coroutine_function():
    """Test is_coroutine_function."""
    charger = OpenEVSE(SERVER_URL)

    async def async_func():
        pass

    def sync_func():
        pass

    assert charger.is_coroutine_function(async_func) is True
    assert charger.is_coroutine_function(sync_func) is False


async def test_callbacks(mock_aioclient):
    """Test both sync and async callbacks."""
    charger = OpenEVSE(SERVER_URL)

    # Async callback
    async_mock = AsyncMock()
    charger.callback = async_mock
    await charger._update_status("data", {"test": 1}, None)
    async_mock.assert_called_once()

    # Sync callback
    sync_mock = MagicMock()
    charger.callback = sync_mock
    with patch.object(charger, "is_coroutine_function", return_value=False):
        await charger._update_status("data", {"test": 2}, None)
    sync_mock.assert_called_once()


async def test_proxies():
    """Test all proxy methods in OpenEVSE."""
    charger = OpenEVSE(SERVER_URL)

    # Firmware proxies
    with patch.object(charger.firmware, "check", AsyncMock(return_value={})) as m:
        await charger.firmware_check()
        m.assert_called_once()
    with patch.object(
        charger.firmware, "version_check", MagicMock(return_value=True)
    ) as m:
        charger.version_check("1.0.0")
        m.assert_called_once()
        charger._version_check("1.0.0")
        assert m.call_count == 2

    # Override proxies
    with patch.object(charger.override, "toggle", AsyncMock()) as m:
        await charger.toggle_override()
        m.assert_called_once()
    with patch.object(charger.override, "clear", AsyncMock()) as m:
        await charger.clear_override()
        m.assert_called_once()

    # Limit proxies
    with patch.object(charger.limit, "set", AsyncMock()) as m:
        await charger.set_limit("type", 10)
        m.assert_called_once()
    with patch.object(charger.limit, "get", AsyncMock()) as m:
        await charger.get_limit()
        m.assert_called_once()
    with patch.object(charger.limit, "clear", AsyncMock()) as m:
        await charger.clear_limit()
        m.assert_called_once()

    # Claims proxies
    with patch.object(charger.claims, "make", AsyncMock()) as m:
        await charger.make_claim()
        m.assert_called_once()
    with patch.object(charger.claims, "release", AsyncMock()) as m:
        await charger.release_claim()
        m.assert_called_once()
    with patch.object(charger.claims, "list", AsyncMock(return_value={})) as m:
        await charger.list_claims()
        m.assert_called_once()

    # Sensors proxies
    with patch.object(charger.sensors, "grid_voltage", AsyncMock()) as m:
        await charger.grid_voltage(230)
        m.assert_called_once()
    with patch.object(charger.sensors, "self_production", AsyncMock()) as m:
        await charger.self_production()
        m.assert_called_once()
    with patch.object(charger.sensors, "soc", AsyncMock()) as m:
        await charger.soc()
        m.assert_called_once()
    with patch.object(charger.sensors, "set_shaper_live_pwr", AsyncMock()) as m:
        await charger.set_shaper_live_pwr(5000)
        m.assert_called_once()


async def test_set_service_level_errors(mock_aioclient, caplog):
    """Test set_service_level error paths."""
    charger = OpenEVSE(SERVER_URL)

    # Invalid level
    with pytest.raises(ValueError):
        await charger.set_service_level(3)

    # API error
    mock_aioclient.post(TEST_URL_CONFIG, status=200, body='{"msg": "failed"}')
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.set_service_level(1)
        assert "Problem issuing command. Response: {'msg': 'failed'}" in caplog.text


async def test_led_brightness(mock_aioclient):
    """Test LED brightness."""
    charger = OpenEVSE(SERVER_URL)

    # Unsupported
    charger._config["version"] = "4.0.0"
    with pytest.raises(UnsupportedFeature):
        await charger.set_led_brightness(100)
    with pytest.raises(UnsupportedFeature):
        _ = charger.led_brightness

    # Supported
    charger._config["version"] = "4.1.0"
    charger._config["led_brightness"] = 128
    mock_aioclient.post(TEST_URL_CONFIG, status=200, body='{"msg": "done"}')
    await charger.set_led_brightness(255)
    assert charger.led_brightness == 128


async def test_set_divert_mode(mock_aioclient):
    """Test set_divert_mode."""
    charger = OpenEVSE(SERVER_URL)

    # Invalid mode
    with pytest.raises(ValueError):
        await charger.set_divert_mode("invalid")

    # Success
    mock_aioclient.post(
        f"http://{SERVER_URL}/divertmode", status=200, body="Divert Mode changed"
    )
    await charger.set_divert_mode("eco")

    # Failure
    mock_aioclient.post(f"http://{SERVER_URL}/divertmode", status=200, body="Error")
    with pytest.raises(UnknownError):
        await charger.set_divert_mode("fast")


async def test_get_charge_current_fallbacks():
    """Test get_charge_current fallbacks."""
    charger = OpenEVSE(SERVER_URL)
    charger._config = {"max_current_soft": 24}
    charger._status = {"pilot": 16}

    # Fallback to max_current_soft
    with patch.object(charger.claims, "list", side_effect=UnsupportedFeature):
        assert await charger.get_charge_current() == 24

    # Fallback to pilot
    charger._config = {}
    with patch.object(charger.claims, "list", side_effect=UnsupportedFeature):
        assert await charger.get_charge_current() == 16


async def test_remaining_properties():
    """Test remaining miscellaneous properties."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {
        "divertmode": 1,
        "shaper_updated": True,
        "mqtt_connected": 0,
        "emoncms_connected": 1,
        "srssi": -50,
        "temp3": 250,
    }
    assert charger.divertmode == "fast"
    charger._status["divertmode"] = 2
    assert charger.divertmode == "eco"
    assert charger.shaper_updated is True
    assert charger.mqtt_connected is False
    assert charger.emoncms_connected == 1
    assert charger.wifi_signal == -50
    assert charger.ir_temperature == 25.0


async def test_get_override_state_more():
    """Test get_override_state edge cases."""
    charger = OpenEVSE(SERVER_URL)

    # Exception
    with patch.object(charger.override, "get", side_effect=UnsupportedFeature):
        assert await charger.get_override_state() is None

    # Fallback to auto
    with patch.object(charger.override, "get", AsyncMock(return_value={})):
        assert await charger.get_override_state() == "auto"


async def test_extra_properties():
    """Test miscellaneous properties."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {
        "state": 3,
        "temp4": 450,
        "total_day": 1000,
        "total_week": 7000,
        "total_month": 30000,
        "total_year": 365000,
        "has_limit": True,
        "ocpp_connected": True,
    }
    charger._config = {"protocol": "1.0"}

    assert charger.state_raw == 3
    assert charger.esp_temperature == 45.0
    assert charger.total_day == 1000
    assert charger.total_week == 7000
    assert charger.total_month == 30000
    assert charger.total_year == 365000
    assert charger.has_limit is True
    assert charger.ocpp_connected is True
    assert charger.protocol_version == "1.0"

    charger._config["protocol"] = "-"
    assert charger.protocol_version is None


async def test_test_and_get_missing_serial(mock_aioclient):
    """Test test_and_get missing serial."""
    mock_aioclient.get(TEST_URL_CONFIG, status=200, body='{"hostname": "test"}')
    charger = OpenEVSE(SERVER_URL)
    with pytest.raises(MissingSerial):
        await charger.test_and_get()


async def test_current_power_unsupported():
    """Test current_power UnsupportedFeature."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "4.2.1"
    with pytest.raises(UnsupportedFeature):
        _ = charger.current_power


async def test_extra_coverage_edge_cases(mock_aioclient, caplog):
    """Reach remaining missing lines in client.py."""
    charger = OpenEVSE(SERVER_URL)

    # 1. Line 151-152: _extract_msg returning None or raw string
    assert charger._extract_msg(123) is None
    assert charger._extract_msg("direct string") == "direct string"

    # 2. Lines 189-190: ws_start when websocket is None
    with caplog.at_level(logging.DEBUG):
        await charger.ws_start()
        assert "Websocket not initialized, creating..." in caplog.text
    # Cleanup websocket
    await charger.ws_disconnect()

    # 3. Lines 495-496: restart_wifi error
    charger._config["version"] = "5.0.0"
    mock_aioclient.post(TEST_URL_RESTART, status=200, body='{"msg": "failed"}')
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.restart_wifi()
        assert "Problem issuing command. Response: {'msg': 'failed'}" in caplog.text

    # 4. Lines 516-517: restart_evse error (RAPI path)
    charger._config["version"] = "4.0.0"
    with patch.object(
        charger, "send_command", AsyncMock(return_value=(True, "failed"))
    ):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(UnknownError):
                await charger.restart_evse()
            assert "Restarting EVSE module via RAPI" in caplog.text
            assert "Problem issuing command. Response: failed" in caplog.text

    # 5. Lines 205 in _start_listening: active_tasks check
    # Start it once - sets self.tasks
    with caplog.at_level(logging.DEBUG):
        await charger.ws_start()

    # State is NOT "connected", so calling ws_start AGAIN will NOT raise AlreadyListening
    # but WILL call _start_listening again, hitting line 205 because self.tasks is set.
    with caplog.at_level(logging.DEBUG):
        await charger.ws_start()
        # Ensure we hit the "Checking for existing active tasks..." area indirectly

    # Now mock it as connected to finally hit AlreadyListening at line 181
    charger.websocket.state = "connected"
    with pytest.raises(AlreadyListening):
        await charger.ws_start()

    # 6. Lines 258 in ws_disconnect: Idempotence return on a FRESH instance
    charger_fresh = OpenEVSE(SERVER_URL)
    await charger_fresh.ws_disconnect()  # Hits line 258 immediately

    # 7. Lines 556-557: set_led_brightness error
    charger._config["version"] = "4.2.0"
    mock_aioclient.post(TEST_URL_CONFIG, status=200, body='{"msg": "failed"}')
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.set_led_brightness(100)
        assert "Problem issuing command. Response: {'msg': 'failed'}" in caplog.text

    # 8. Lines 697-699: state property with invalid state_idx
    charger._status["state"] = "invalid"
    with caplog.at_level(logging.DEBUG):
        assert charger.state == "unknown"
        assert "Invalid state value: invalid" in caplog.text

    # 9. Lines 716-718: status property branches
    charger._status = {"status": "present"}
    assert charger.status == "present"
    charger._status = {"state": 3}  # Charging
    assert charger.status == "charging"


async def test_set_divert_mode_error_coverage(mock_aioclient, caplog):
    """Line 547 coverage (set_divert_mode error path)."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "4.2.2"

    mock_aioclient.post(
        f"http://{SERVER_URL}/divertmode", status=200, body='{"msg": "failed"}'
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.set_divert_mode("fast")
        assert "Problem issuing command. Response: {'msg': 'failed'}" in caplog.text


async def test_set_current_rapi_error(test_charger, caplog):
    """Test set_current with RAPI error ($NK)."""
    # Force RAPI path (no override endpoint)
    test_charger._config["version"] = "2.9.0"

    # Mock send_command to return $NK
    with patch.object(
        test_charger, "send_command", AsyncMock(return_value=(True, "$NK^21"))
    ):
        with caplog.at_level(logging.ERROR):
            result = await test_charger.set_current(15)
            assert result is False
            assert "Problem setting current limit. Response: $NK^21" in caplog.text

    # Mock send_command to return success=False
    with patch.object(
        test_charger, "send_command", AsyncMock(return_value=(False, "timeout"))
    ):
        with caplog.at_level(logging.ERROR):
            result = await test_charger.set_current(15)
            assert result is False
            assert "Problem setting current limit. Response: timeout" in caplog.text
