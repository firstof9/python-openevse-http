"""Tests for OpenEVSE Client."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from freezegun import freeze_time

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.client import UPDATE_TRIGGERS
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
    OpenEVSEWebsocket,
)
from tests.common import load_fixture
from tests.const import (
    SERVER_URL,
    TEST_URL_CONFIG,
    TEST_URL_RAPI,
    TEST_URL_RESTART,
    TEST_URL_STATUS,
)

pytestmark = pytest.mark.asyncio


async def test_update_status(test_charger):
    """Verify that _update_status correctly updates the internal status dictionary."""
    data = json.loads(load_fixture("v4_json/status.json"))
    await test_charger._update_status("data", data, None)
    assert test_charger._status == data


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "sleeping"), ("test_charger_v2", "not connected")],
)
async def test_get_status(fixture, expected, request):
    """Verify that the status property returns the expected state string."""
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
    """Verify that the wifi_ssid property returns the expected SSID."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_ssid
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "7.1.3"), ("test_charger_v2", "5.0.1")]
)
async def test_get_firmware(fixture, expected, request):
    """Verify that the openevse_firmware property returns the expected version string."""
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
    """Verify that the hostname property returns the expected device hostname."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.hostname
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_ammeter_offset(fixture, expected, request):
    """Verify that the ammeter_offset property returns the expected calibration offset."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    await charger.ws_disconnect()
    status = charger.ammeter_offset
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 220), ("test_charger_v2", 220)]
)
async def test_get_ammeter_scale_factor(fixture, expected, request):
    """Verify that the ammeter_scale_factor property returns the expected scale factor."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ammeter_scale_factor
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 2), ("test_charger_v2", 2)]
)
async def test_get_service_level(fixture, expected, request):
    """Verify that the service_level property returns the expected charging level (1 or 2)."""
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
    """Verify that the wifi_firmware property returns the expected version string."""
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
    """Verify that the ip_address property returns the expected IP string."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ip_address
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 240), ("test_charger_v2", 240)]
)
async def test_get_charging_voltage(fixture, expected, request):
    """Verify that the charging_voltage property returns the expected voltage in volts."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_voltage
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "STA"), ("test_charger_v2", "STA")]
)
async def test_get_mode(fixture, expected, request):
    """Verify that the mode property returns the expected operating mode."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.mode
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_using_ethernet(fixture, expected, request):
    """Verify that the using_ethernet property correctly indicates Ethernet connectivity."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.using_ethernet
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_stuck_relay_trip_count(fixture, expected, request):
    """Verify that the stuck_relay_trip_count property returns the expected count."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.stuck_relay_trip_count
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_no_gnd_trip_count(fixture, expected, request):
    """Verify that the no_gnd_trip_count property returns the expected count."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.no_gnd_trip_count
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 1), ("test_charger_v2", 0)]
)
async def test_get_gfi_trip_count(fixture, expected, request):
    """Verify that the gfi_trip_count property returns the expected count."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.gfi_trip_count
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 246), ("test_charger_v2", 8751)]
)
async def test_get_charge_time_elapsed(fixture, expected, request):
    """Verify that the charge_time_elapsed property returns the expected duration in seconds."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charge_time_elapsed
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", -61), ("test_charger_v2", -56)]
)
async def test_get_wifi_signal(fixture, expected, request):
    """Verify that the wifi_signal property returns the expected RSSI value."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_signal
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 32.2), ("test_charger_v2", 0)]
)
async def test_get_charging_current(fixture, expected, request):
    """Verify that the charging_current property returns the expected current in amperes."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 25)]
)
async def test_get_current_capacity(fixture, expected, request):
    """Verify that the current_capacity property returns the expected maximum current."""
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
    """Verify that the usage_total property returns the expected total energy usage."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.usage_total
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 50.3), ("test_charger_v2", 34.0)]
)
async def test_get_ambient_temperature(fixture, expected, request):
    """Verify that the ambient_temperature property returns the expected temperature in Celsius."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ambient_temperature
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 50.3), ("test_charger_v2", None)]
)
async def test_get_rtc_temperature(fixture, expected, request):
    """Verify that the rtc_temperature property returns the expected RTC temperature."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.rtc_temperature
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", None)]
)
async def test_get_ir_temperature(fixture, expected, request):
    """Verify that the ir_temperature property returns the expected IR temperature."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ir_temperature
    assert status is None
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 56.0), ("test_charger_v2", None)]
)
async def test_get_esp_temperature(fixture, expected, request):
    """Verify that the esp_temperature property returns the expected ESP32 temperature."""
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
    """Verify that the time property correctly parses and returns the device time as a datetime object."""
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
    """Verify that the usage_session property returns the expected energy usage for the current session."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.usage_session
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", "4.0.1")]
)
async def test_get_protocol_version(fixture, expected, request):
    """Verify that the protocol_version property returns the expected RAPI version."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.protocol_version
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 6), ("test_charger_v2", 6)]
)
async def test_get_min_amps(fixture, expected, request):
    """Verify that the min_amps property returns the expected minimum current limit."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.min_amps
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 48)]
)
async def test_get_max_amps(fixture, expected, request):
    """Verify that the max_amps property returns the expected maximum current limit."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.max_amps
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_ota_update(fixture, expected, request):
    """Verify that the ota_update property correctly indicates if an update is available."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ota_update
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize("fixture, expected", [("test_charger", True)])
async def test_get_vehicle(fixture, expected, request):
    """Verify that the vehicle property correctly indicates if a vehicle is connected."""
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
    """Verify that the state property returns the expected charger state string."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.state
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_tempt(fixture, expected, request):
    """Verify that the temp_check_enabled property returns the expected boolean status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.temp_check_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", True)]
)
async def test_get_diodet(fixture, expected, request):
    """Verify that the diode_check_enabled property returns the expected boolean status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.diode_check_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_ventt(fixture, expected, request):
    """Verify that the vent_required_enabled property returns the expected boolean status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vent_required_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_groundt(fixture, expected, request):
    """Verify that the ground_check_enabled property returns the expected boolean status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ground_check_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_relayt(fixture, expected, request):
    """Verify that the stuck_relay_check_enabled property returns the expected boolean status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.stuck_relay_check_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_charge_rate(fixture, expected, request):
    """Verify that the charge_rate property returns the expected charging rate."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charge_rate
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", None)]
)
async def test_get_available_current(fixture, expected, request):
    """Verify that the available_current property returns the expected available current."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.available_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", None)]
)
async def test_get_smoothed_available_current(fixture, expected, request):
    """Verify that the smoothed_available_current property returns the expected value."""
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
    """Verify that the divert_active property returns the expected status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.divert_active
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_manual_override(fixture, expected, request):
    """Verify that the manual_override property returns the expected status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.manual_override
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "1234567890AB"), ("test_charger_v2", None)]
)
async def test_wifi_serial(fixture, expected, request):
    """Verify that the wifi_serial property returns the expected serial number."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_serial
    assert status == expected
    await charger.ws_disconnect()


async def test_set_current(test_charger, mock_aioclient, caplog):
    """Verify that set_current correctly updates the current limit via the override API."""
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
        await test_charger.set_current(12)
    assert "Setting current limit to 12" in caplog.text


async def test_set_current_error(
    test_charger, test_charger_broken, mock_aioclient, caplog
):
    """Ensure set_current raises ValueError for invalid inputs or fails appropriately when firmware is missing."""
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
        body='{"cmd": "OK", "ret": "$OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_broken.set_current(24)
    assert "Unable to find firmware version." in caplog.text


async def test_divert_mode_missing_ok(mock_aioclient):
    """Test divert mode with missing 'ok' field in response."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "2.9.1"
    charger._config["divert_enabled"] = False

    # Mock success (missing 'ok', but has 'msg')
    mock_aioclient.post(
        f"http://{SERVER_URL}/config", status=200, body='{"msg": "done"}'
    )

    result = await charger.divert_mode()
    assert result["msg"] == "done"
    assert charger._config["divert_enabled"] is True


async def test_divert_mode_strict_fail(mock_aioclient, caplog):
    """Test divert mode with strict success marker requirement."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "2.9.1"
    charger._config["divert_enabled"] = False

    # Mock success 'ok' but failing 'msg'
    mock_aioclient.post(
        f"http://{SERVER_URL}/config", status=200, body='{"ok": true, "msg": "failed"}'
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.divert_mode()
    assert "Problem toggling divert: {'ok': True, 'msg': 'failed'}" in caplog.text
    # Ensure cache NOT flipped
    assert charger._config["divert_enabled"] is False


async def test_set_current_v2(
    test_charger_v2, test_charger_dev, mock_aioclient, caplog
):
    """Verify that set_current correctly uses the RAPI interface for older firmware versions."""
    await test_charger_v2.update()
    test_charger_v2.requester.set_update_callback(None)
    value = {"cmd": "OK", "ret": "$OK"}
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
    """Verify that the charging_power property returns the expected power in Watts."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.charging_power
    assert status == expected
    await charger.ws_disconnect()


async def test_set_divertmode_v4(test_charger_new, mock_aioclient, caplog):
    """Verify that divert_mode correctly toggles the setting on v4 firmware."""
    await test_charger_new.update()
    value = '{"ok": true, "msg": "done"}'
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.divert_mode()
        assert "Toggling divert: True" in caplog.text

    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    test_charger_new._config["divert_enabled"] = True
    with caplog.at_level(logging.DEBUG):
        await test_charger_new.divert_mode()
        assert "Toggling divert: False" in caplog.text


async def test_set_divertmode_v2(test_charger_v2, mock_aioclient):
    await test_charger_v2.update()
    value = '{"ok": true, "msg": "done"}'
    mock_aioclient.post(
        TEST_URL_CONFIG,
        status=200,
        body=value,
    )
    await test_charger_v2.divert_mode()


async def test_set_divertmode_broken(test_charger_broken):
    await test_charger_broken.update()
    test_charger_broken._config["version"] = "4.1.8"
    with pytest.raises(UnsupportedFeature):
        await test_charger_broken.divert_mode()


async def test_set_divertmode_unknown_semver(test_charger_unknown_semver, caplog):
    # Handle non-semver firmware versions gracefully
    test_charger_unknown_semver._config = {"version": "not-semver"}
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_unknown_semver.divert_mode()
    assert "Non-semver firmware version detected." in caplog.text


async def test_test_and_get(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Verify that test_and_get correctly identifies device serial and model or raises MissingSerial on old firmware."""
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )
    data = await test_charger.test_and_get()
    assert data["serial"] == "1234567890AB"
    assert data["model"] == "unknown"

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(MissingSerial):
            await test_charger_v2.test_and_get()
    assert "Older firmware detected, missing serial." in caplog.text


async def test_restart_wifi(test_charger_modified_ver, mock_aioclient, caplog):
    """Verify that restart_wifi correctly sends the restart command to the gateway."""
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
    """Verify that restart_evse correctly sends the restart command to the EVSE module."""
    await test_charger_v2.update()
    test_charger_v2.requester.set_update_callback(None)
    value = {"cmd": "OK", "ret": "$OK"}
    mock_aioclient.post(
        "http://openevse.test.tld/r",
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_v2.restart_evse()
    assert "EVSE Restart response: $OK" in caplog.text
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
    """Verify that the shaper_active property returns the expected boolean status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.shaper_active
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 2299), ("test_charger_v2", None)]
)
async def test_shaper_live_power(fixture, expected, request):
    """Verify that the shaper_live_power property returns the expected value."""
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
    """Verify that the shaper_available_current property returns the expected value."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.shaper_available_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 4000), ("test_charger_v2", None)]
)
async def test_shaper_max_power(fixture, expected, request):
    """Verify that the shaper_max_power property returns the expected value."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.shaper_max_power
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 75), ("test_charger_v2", None)]
)
async def test_vehicle_soc(fixture, expected, request):
    """Verify that the vehicle_soc property returns the expected battery state of charge."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vehicle_soc
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 468), ("test_charger_v2", None)]
)
async def test_vehicle_range(fixture, expected, request):
    """Verify that the vehicle_range property returns the expected estimated range."""
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
    """Verify that the vehicle_eta property correctly calculates the estimated completion time."""
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
    """Verify that the max_current_soft property returns the expected soft limit."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.max_current_soft
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", 48), ("test_charger_v2", None)]
)
async def test_max_current(fixture, expected, request):
    """Verify that the max_current property returns the expected maximum current."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.max_current
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", False), ("test_charger_v2", False)]
)
async def test_emoncms_connected(fixture, expected, request):
    """Verify that the emoncms_connected property correctly indicates server status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.emoncms_connected
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", False), ("test_charger_v2", None)]
)
async def test_ocpp_connected(fixture, expected, request):
    """Verify that the ocpp_connected property correctly indicates server status."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ocpp_connected
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", 1208725), ("test_charger_v2", None)]
)
async def test_uptime(fixture, expected, request):
    """Verify that the uptime property returns the expected device uptime in seconds."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.uptime
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger_new", 167436), ("test_charger_v2", None)]
)
async def test_freeram(fixture, expected, request):
    """Verify that the freeram property returns the expected free memory available."""
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
    """Verify that the checks_count property returns the internal trip counters dictionary."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.checks_count
    assert status == expected
    await charger.ws_disconnect()


async def test_get_override_state(test_charger_new, mock_aioclient):
    """Verify that get_override_state returns the expected override mode string."""
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
    """Verify that the current_power property returns the expected power in Watts."""
    await test_charger_new.update()
    status = test_charger_new.current_power
    assert status == 4500
    await test_charger_new.ws_disconnect()


async def test_get_charge_current(test_charger_new, mock_aioclient):
    """Verify that get_charge_current returns the active target from claims."""
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

    with (
        patch("asyncio.get_running_loop", side_effect=RuntimeError),
        patch("asyncio.new_event_loop") as mock_new_loop,
        patch("asyncio.set_event_loop") as mock_set_loop,
        patch(
            "openevsehttp.websocket.OpenEVSEWebsocket.listen", new_callable=AsyncMock
        ),
        patch.object(OpenEVSE, "repeat", new_callable=AsyncMock),
    ):
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop
        await charger._start_listening()
        assert charger._loop == mock_loop
        mock_set_loop.assert_called_once_with(mock_loop)


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

    # Test stopped WITHOUT error
    await charger._update_status(SIGNAL_CONNECTION_STATE, STATE_CONNECTED, None)
    assert charger._ws_listening is True
    await charger._update_status(SIGNAL_CONNECTION_STATE, STATE_STOPPED, None)
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
        mock_state.side_effect = ["connected", "connected", "stopped"]

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
    """Verify that set_charge_mode correctly updates the device charging mode via the config API."""
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
    charger.requester._update_callback = None
    await charger.set_led_brightness(255)
    assert charger.led_brightness == 128


async def test_set_divert_mode(mock_aioclient):
    """Test set_divert_mode."""
    charger = OpenEVSE(SERVER_URL)

    # Invalid mode
    with pytest.raises(ValueError):
        await charger.set_divert_mode("invalid")

    # Success
    with patch.object(charger, "full_refresh", AsyncMock()):
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
    assert charger.emoncms_connected is True
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


async def async_stub(*args, **kwargs):
    """Empty async stub."""
    pass


async def async_pending_stub(event: asyncio.Event, *args, **kwargs):
    """Async stub that waits on an event."""
    await event.wait()


async def test_extra_coverage_edge_cases(mock_aioclient, caplog):
    """Reach remaining missing lines in client.py."""
    charger = OpenEVSE(SERVER_URL)

    # 1. _extract_msg returning None or raw string
    assert charger._extract_msg(123) is None
    assert charger._extract_msg("direct string") == "direct string"

    # 2. ws_start when websocket is None and orphan cleanup
    stop_event = asyncio.Event()

    async def pending_stub(*args, **kwargs):
        await async_pending_stub(stop_event, *args, **kwargs)

    with (
        patch(
            "openevsehttp.websocket.OpenEVSEWebsocket.listen",
            side_effect=pending_stub,
        ),
        patch.object(OpenEVSE, "repeat", side_effect=pending_stub),
        caplog.at_level(logging.DEBUG),
    ):
        await charger.ws_start()
        assert "Websocket not initialized or stopped, creating..." in caplog.text

        # Now task is active. Call ws_start AGAIN to trigger orphan check.
        # Force _ws_listening to False so it attempts setup again
        charger._ws_listening = False
        await charger.ws_start()
        assert "Cleaning up orphaned websocket tasks before restart..." in caplog.text

    # Signal tasks to finish and clean up
    stop_event.set()
    await charger.ws_disconnect()

    # 3. test_and_get ok: False
    mock_aioclient.get(
        TEST_URL_CONFIG, status=200, body='{"ok": false, "msg": "failed"}'
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.test_and_get()
    assert "Problem getting config for serial detection" in caplog.text
    caplog.clear()

    # 4. restart_wifi error
    charger._config["version"] = "5.0.0"
    mock_aioclient.post(TEST_URL_RESTART, status=200, body='{"msg": "failed"}')
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.restart_wifi()
    assert "Problem issuing command. Response: {'msg': 'failed'}" in caplog.text
    caplog.clear()

    # 5. restart_evse RAPI failure path
    charger._config["version"] = "4.0.0"
    with patch.object(charger, "send_command", return_value=("", "$NK")):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(UnknownError):
                await charger.restart_evse()
        assert "Problem issuing command. Response: " in caplog.text
    caplog.clear()

    # 6. restart_evse HTTP failure path (5.0.0+)
    charger._config["version"] = "5.0.0"
    mock_aioclient.post(TEST_URL_RESTART, status=200, body='{"msg": "failed"}')
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.restart_evse()
    assert "Problem issuing command. Response: failed" in caplog.text
    caplog.clear()

    # 7. Various property edge cases (missing data in cache)
    charger._config = {}
    charger._status = {}
    assert charger.ammeter_offset is None
    assert charger.service_level is None
    assert charger.rtc_temperature is None
    assert charger.ir_temperature is None
    assert charger.openevse_firmware is None
    assert charger.charging_power is None
    assert charger.charge_rate is None
    assert charger.smoothed_available_current is None
    assert charger.available_current is None
    assert charger.charging_current is None
    assert charger.stuck_relay_trip_count is None
    assert charger.no_gnd_trip_count is None
    assert charger.gfi_trip_count is None
    assert charger.status == "unknown"  # defaults to self.state (0)

    # 8. led_brightness error path
    charger._config["version"] = "5.0.0"
    mock_aioclient.post(TEST_URL_CONFIG, status=200, body='{"msg": "failed"}')
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.set_led_brightness(100)
    assert "Problem issuing command. Response: {'msg': 'failed'}" in caplog.text
    caplog.clear()

    # Cleanup any remaining test state
    await charger.ws_disconnect()

    # Use a mock instead of real OpenEVSEWebsocket to avoid ClientSession allocation
    async def noop():
        pass

    charger.websocket = MagicMock(spec=OpenEVSEWebsocket)
    charger.websocket.listen = noop
    charger.websocket.keepalive = noop
    charger.websocket.state = "disconnected"

    # Prepare charger.tasks to exercise orphan-task cleanup
    charger.tasks = set()
    charger.tasks.add(asyncio.create_task(noop()))

    with caplog.at_level(logging.DEBUG):
        await charger.ws_start()
        assert "Cleaning up orphaned websocket tasks before restart..." in caplog.text

    # Cancel background tasks to avoid leak, but keep mocked websocket for next check
    for task in list(charger.tasks):
        task.cancel()
    await asyncio.gather(*charger.tasks, return_exceptions=True)
    charger.tasks = set()

    # Mock as connected to trigger AlreadyListening branch
    charger.websocket.state = "connected"
    charger._ws_listening = True
    with pytest.raises(AlreadyListening):
        await charger.ws_start()

    # Verify recreation of stopped websocket (fix for reuse bug)
    charger.websocket.state = STATE_STOPPED
    first_ws = charger.websocket
    await charger.ws_start()
    assert charger.websocket is not first_ws
    # Cleanup tasks from the new websocket
    for task in list(charger.tasks):
        task.cancel()
    await asyncio.gather(*charger.tasks, return_exceptions=True)
    charger.tasks = set()

    # Verify idempotence on a fresh instance
    charger_fresh = OpenEVSE(SERVER_URL)
    await charger_fresh.ws_disconnect()  # Disconnect immediately

    # Verify led_brightness error handling
    charger._config["version"] = "4.2.0"
    mock_aioclient.post(TEST_URL_CONFIG, status=200, body='{"msg": "failed"}')
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.set_led_brightness(100)
    assert "Problem issuing command. Response: {'msg': 'failed'}" in caplog.text
    caplog.clear()

    # Verify state property invalid index handling
    charger._status["state"] = "invalid"
    with caplog.at_level(logging.DEBUG):
        assert charger.state == "unknown"
        assert "Invalid state value: invalid" in caplog.text

    # Verify status property branch handling
    charger._status = {"status": "present"}
    assert charger.status == "present"
    charger._status = {"state": 3}  # Charging
    assert charger.status == "charging"


async def test_set_divert_mode_error_coverage(mock_aioclient, caplog):
    """Verify set_divert_mode error handling."""
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
        test_charger, "send_command", AsyncMock(return_value=("$SC 15 V", "$NK^21"))
    ):
        with caplog.at_level(logging.ERROR):
            result = await test_charger.set_current(15)
            assert result is False
            assert (
                "Problem setting current limit. Response: ('$SC 15 V', '$NK^21')"
                in caplog.text
            )

    # Mock send_command to return success=False (e.g. via $NK in command field)
    with patch.object(
        test_charger, "send_command", AsyncMock(return_value=("$NK", "timeout"))
    ):
        with caplog.at_level(logging.ERROR):
            result = await test_charger.set_current(15)
            assert result is False
            assert (
                "Problem setting current limit. Response: ('$NK', 'timeout')"
                in caplog.text
            )


async def test_callback_exception(test_charger, caplog):
    """Test that a callback exception does not crash the receive loop."""

    async def callback():
        raise Exception("Callback error")

    test_charger.set_update_callback(callback)
    with caplog.at_level(logging.ERROR):
        await test_charger._update_status("data", {"mode": 1}, None)
        assert "Exception in user callback: Callback error" in caplog.text


async def test_divert_mode_server_error(mock_aioclient, caplog):
    """Test divert_mode with server 'ok': False response."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "2.9.1"
    charger._config["divert_enabled"] = False

    mock_aioclient.post(
        f"http://{SERVER_URL}/config",
        status=200,
        body='{"ok": false, "msg": "Toggling divert failed"}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(UnknownError):
            await charger.divert_mode()
    assert (
        "Problem toggling divert: {'ok': False, 'msg': 'Toggling divert failed'}"
        in caplog.text
    )


async def test_client_none_safeguards(mock_aioclient):
    """Test safety paths when websocket or config is None."""
    charger = OpenEVSE(SERVER_URL)

    # Verify ws_state when no websocket set
    charger.websocket = None
    assert charger.ws_state == "stopped"

    # Verify divert_mode when no config available
    charger._config = None
    with pytest.raises(UnsupportedFeature):
        await charger.divert_mode()


async def test_update_failure_cache_preservation(mock_aioclient):
    """Verify that update() preserves cache data on network failure."""
    charger = OpenEVSE(SERVER_URL)
    # Initial success to establish a state
    mock_aioclient.get(
        TEST_URL_STATUS, status=200, body=load_fixture("v4_json/status.json")
    )
    mock_aioclient.get(
        TEST_URL_CONFIG, status=200, body=load_fixture("v4_json/config.json")
    )
    await charger.update()

    # fixture status.json has "status": "sleeping"
    assert charger.state == "sleeping"

    # Subsequent failure should not change it
    mock_aioclient.get(
        TEST_URL_STATUS, status=200, body='{"ok": false, "msg": "failed"}'
    )
    mock_aioclient.get(
        TEST_URL_CONFIG, status=200, body='{"ok": false, "msg": "failed"}'
    )
    await charger.update()
    # Should stay as 'sleeping'
    assert charger.state == "sleeping"


async def test_get_override_state_fail(mock_aioclient, caplog):
    """Test get_override_state with failed response."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "4.2.0"
    mock_aioclient.get(
        f"http://{SERVER_URL}/override",
        status=200,
        body='{"ok": false, "msg": "failed"}',
    )
    with caplog.at_level(logging.ERROR):
        result = await charger.get_override_state()
        assert result is None
    assert "Problem getting status for override state" in caplog.text


async def test_set_current_transport_fail(caplog):
    """Test set_current with transport failure (False, msg)."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "2.9.0"
    with patch.object(charger, "send_command", return_value=(False, "timeout")):
        with caplog.at_level(logging.ERROR):
            assert await charger.set_current(16) is False
        assert (
            "Problem setting current limit. Response: (False, 'timeout')" in caplog.text
        )


async def test_websocket_update_exception_handling(caplog):
    """Verify update failure during websocket status push."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "4.0.0"
    trigger_key = next(iter(UPDATE_TRIGGERS))
    data = {trigger_key: "value"}

    with (
        patch.object(charger, "update", side_effect=Exception("Update failed")),
        caplog.at_level(logging.ERROR),
    ):
        # Directly call _update_status - it expects (msgtype, data, error)
        await charger._update_status("data", data, None)
        assert "Update failed during websocket push" in caplog.text


async def test_websocket_non_mapping_payload(caplog):
    """Test websocket with non-mapping payload."""
    charger = OpenEVSE(SERVER_URL)
    with caplog.at_level(logging.WARNING):
        await charger._update_status("data", "not a dict", None)
    assert "Non-mapping websocket payload: not a dict" in caplog.text


async def test_set_current_rapi_dict_error(mock_aioclient):
    """Verify set_current handling of RAPI dict error."""
    charger = OpenEVSE(SERVER_URL)
    # Force RAPI branch
    charger._config["version"] = "2.9.0"

    # requester.py handles returning dict if ok=False
    mock_aioclient.post(
        TEST_URL_RAPI, status=200, body='{"ok": false, "msg": "transport error"}'
    )
    result = await charger.set_current(16)
    assert result is False


async def test_restart_evse_rapi_dict_error(mock_aioclient):
    """Verify restart_evse handling of RAPI dict error."""
    charger = OpenEVSE(SERVER_URL)
    # Force RAPI branch
    charger._config["version"] = "4.1.0"

    mock_aioclient.post(
        TEST_URL_RAPI, status=200, body='{"ok": false, "msg": "transport error"}'
    )
    with pytest.raises(UnknownError):
        await charger.restart_evse()


async def test_test_and_get_html_response(mock_aioclient):
    """Test test_and_get when receiving an HTML response."""
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body="<html><body>Not JSON</body></html>",
    )
    charger = OpenEVSE(SERVER_URL)
    with pytest.raises(UnknownError):
        await charger.test_and_get()


async def test_get_charge_current_malformed_claim(mock_aioclient):
    """Test get_charge_current with malformed claims response."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["max_current_hard"] = 32
    charger._config["max_current_soft"] = 16
    charger._status["pilot"] = 10

    # Mock list_claims returning empty dict
    with patch.object(charger, "list_claims", AsyncMock(return_value={})):
        assert await charger.get_charge_current() == 16

    # Mock list_claims returning non-dict properties
    with patch.object(
        charger, "list_claims", AsyncMock(return_value={"properties": None})
    ):
        assert await charger.get_charge_current() == 16

    # Mock list_claims returning missing charge_current
    with patch.object(
        charger, "list_claims", AsyncMock(return_value={"properties": {}})
    ):
        assert await charger.get_charge_current() == 16


async def test_get_charge_current_missing_max_current_hard(mock_aioclient):
    """Test get_charge_current when max_current_hard is missing."""
    charger = OpenEVSE(SERVER_URL)
    charger._config = {"max_current_soft": 16}
    charger._status["pilot"] = 10

    # Mock list_claims success, but config missing key
    with patch.object(
        charger,
        "list_claims",
        AsyncMock(return_value={"properties": {"charge_current": 24}}),
    ):
        assert await charger.get_charge_current() == 16


async def test_update_ignores_message_only_response(mock_aioclient):
    """Test update() ignores "message-only" envelopes (e.g. from Requester error)."""
    charger = OpenEVSE(SERVER_URL)
    # Success first
    mock_aioclient.get(
        TEST_URL_STATUS, status=200, body='{"status": "present", "state": 3}'
    )
    mock_aioclient.get(TEST_URL_CONFIG, status=200, body='{"version": "5.0.0"}')
    await charger.update()
    assert charger.status == "present"

    # Now mock status returning non-JSON (HTML/Plain text), which Requester wraps in {"msg": ...}
    # Current behavior will assign it to _status
    mock_aioclient.get(TEST_URL_STATUS, status=200, body="not JSON")
    mock_aioclient.get(TEST_URL_CONFIG, status=200, body='{"version": "5.0.0"}')
    await charger.update()

    # We want it to stay as 'present' instead of being corrupted
    assert charger.status == "present"


async def test_ws_state(test_charger):
    """Test ws_state property."""
    assert test_charger.ws_state == "stopped"  # default when websocket is None
    test_charger.websocket = MagicMock()
    test_charger.websocket.state = "connected"
    assert test_charger.ws_state == "connected"


async def test_get_charge_current_ok_false(mock_aioclient):
    """Test get_charge_current when claims return ok: False."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["max_current_hard"] = 32
    charger._config["max_current_soft"] = 16
    charger._status["pilot"] = 10

    # Mock list_claims returning 'ok: False' (failure) but with properties
    # Current behavior will use '5', we want it to fall back to '16'
    with patch.object(
        charger,
        "list_claims",
        AsyncMock(return_value={"ok": False, "properties": {"charge_current": 5}}),
    ):
        assert await charger.get_charge_current() == 16


async def test_set_current_failure_envelope(mock_aioclient):
    """Test set_current when API returns failure envelope without 'ok' key."""
    # Mock required endpoints for update() and initial state
    mock_aioclient.get(
        f"http://{SERVER_URL}/status",
        status=200,
        body='{"state": 1, "status": "sleeping"}',
    )
    mock_aioclient.get(
        f"http://{SERVER_URL}/config",
        status=200,
        body='{"version": "4.1.2", "min_current_hard": 6, "max_current_hard": 32}',
    )
    mock_aioclient.get(
        f"http://{SERVER_URL}/override", status=200, body='{"state": "disabled"}'
    )

    charger = OpenEVSE(SERVER_URL)
    await charger.update()

    # Mock response that doesn't have 'ok' but indicates failure
    mock_aioclient.post(
        f"http://{SERVER_URL}/override", status=200, body='{"msg": "failed"}'
    )

    # This should now raise UnknownError
    with pytest.raises(UnknownError):
        await charger.set_current(10)


async def test_mutator_ignoring_ok_false(mock_aioclient):
    """Test that mutators (e.g. set_charge_mode) incorrectly succeed if 'ok' is False but 'msg' is 'done'."""
    mock_aioclient.get(
        f"http://{SERVER_URL}/status", status=200, body='{"status": "sleeping"}'
    )
    mock_aioclient.get(
        f"http://{SERVER_URL}/config", status=200, body='{"version": "4.1.0"}'
    )
    charger = OpenEVSE(SERVER_URL)
    await charger.update()

    # Mock response with ok: False but message that looks successful
    mock_aioclient.post(
        f"http://{SERVER_URL}/config", status=200, body='{"ok": false, "msg": "done"}'
    )

    # We want this to raise UnknownError, and it now correctly does
    with pytest.raises(UnknownError):
        await charger.set_charge_mode("eco")


async def test_get_override_state_msg_only(mock_aioclient, caplog):
    """Test get_override_state when response is message-only (e.g. error)."""
    charger = OpenEVSE(SERVER_URL)
    charger._config["version"] = "4.2.0"
    # Mock message-only response (e.g. from Requester normalization of non-JSON)
    # This currently returns 'auto', but we want it to return None and log error.
    mock_aioclient.get(
        f"http://{SERVER_URL}/override",
        status=200,
        body='{"msg": "failed"}',
    )
    with caplog.at_level(logging.ERROR):
        result = await charger.get_override_state()
        assert result is None
    assert "Problem getting status for override state" in caplog.text


async def test_repeat_exit_during_sleep():
    """Test that repeat loop exits if state becomes stopped during sleep."""
    charger = OpenEVSE(SERVER_URL)
    func = AsyncMock()

    # Set initial state via mocked websocket
    charger.websocket = MagicMock()
    charger.websocket.state = "connected"

    # Start repeat in a task with a long sleep
    task = asyncio.create_task(charger.repeat(0.5, func))

    # Give it time to start sleeping
    await asyncio.sleep(0.1)

    # Stop it
    charger.websocket.state = "stopped"

    # Wait for task to finish
    await task

    # If fixed, func was never called because we stopped it during sleep.
    func.assert_not_called()


async def test_client_extract_msg_edge_cases():
    """Test _extract_msg with various input types."""
    charger = OpenEVSE("openevse.test.tld")
    assert charger._extract_msg("direct string") == "direct string"
    assert charger._extract_msg(123) is None


async def test_client_set_current_error_handling(caplog):
    """Test set_current error handling and logging."""
    charger = OpenEVSE("openevse.test.tld")
    charger.requester = MagicMock()
    charger.send_command = AsyncMock(return_value="$EX")

    # Handle missing hard current limits configuration
    charger._version_check = lambda v: True
    charger._config = {"min_current_hard": None, "max_current_hard": 40}
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="Hard current limits are missing"):
            await charger.set_current(10)
    assert "Missing current limits in config" in caplog.text

    # Handle invalid value out of hard limits range
    charger._config = {"min_current_hard": 6, "max_current_hard": 40}
    with pytest.raises(ValueError):
        await charger.set_current(5)

    # Handle RAPI failure during current set
    charger._version_check = lambda v: False
    assert await charger.set_current(10) is False


async def test_client_setter_unknown_errors():
    """Test various setters raising UnknownError on failure."""
    charger = OpenEVSE("openevse.test.tld")
    charger.requester = MagicMock()
    charger.requester.process_request = AsyncMock(
        return_value={"ok": False, "msg": "failed"}
    )

    with pytest.raises(UnknownError):
        await charger.set_charge_mode("fast")
    with pytest.raises(UnknownError):
        await charger.set_service_level(1)


async def test_client_property_edge_cases():
    """Test property accessors with malformed or missing status data."""
    charger = OpenEVSE("openevse.test.tld")

    # Handle state fallback for invalid index
    charger._status = {"state": "invalid"}
    assert charger.state == "unknown"

    # Handle Wifi signal with invalid data
    charger._status = {"srssi": "invalid"}
    assert charger.wifi_signal is None
    charger._status = {}
    assert charger.wifi_signal is None

    # Handle ambient temp with boolean data fallback
    charger._status = {"temp": True, "temp1": False}
    assert charger.ambient_temperature is None

    # Handle service level edge cases
    charger._config = {"service": "invalid"}
    assert charger.service_level is None
    charger._config = {}
    assert charger.service_level is None


async def test_client_test_and_get_error():
    """Verify that test_and_get raises UnknownError on failure."""
    charger = OpenEVSE("openevse.test.tld")
    charger.requester = MagicMock()
    charger.requester.process_request = AsyncMock(return_value={"ok": False})
    with pytest.raises(UnknownError):
        await charger.test_and_get()


async def test_client_update_failure_path(caplog):
    """Verify update method exception handling."""
    charger = OpenEVSE("openevse.test.tld")
    charger.requester = MagicMock()
    charger.requester.process_request = AsyncMock(side_effect=Exception("Failed"))
    with pytest.raises(Exception, match="Failed"):
        await charger.update()


async def test_client_ws_disconnect_task_cleanup():
    """Verify task cleanup during websocket disconnection."""
    charger = OpenEVSE("openevse.test.tld")
    charger.websocket = MagicMock()
    charger.websocket.close = AsyncMock()
    charger._loop = asyncio.get_running_loop()

    async def dummy():
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(dummy())
    charger.tasks = [task]
    await charger.ws_disconnect()
    assert task.cancelled() or task.done()


async def test_client_rapi_fallback_errors():
    """Test legacy RAPI fallback commands returning False (failure)."""
    charger = OpenEVSE("openevse.test.tld")
    charger.requester = MagicMock()
    # set_current returns False on failure in RAPI path
    charger.requester.send_command = AsyncMock(return_value="$EX")
    charger._version_check = lambda v: False

    assert await charger.set_current(10) is False


async def test_client_restart_wifi_errors():
    """Verify restart_wifi error handling."""
    charger = OpenEVSE("openevse.test.tld")
    charger.requester = MagicMock()
    charger.requester.process_request = AsyncMock(return_value={"ok": False})
    with pytest.raises(UnknownError):
        await charger.restart_wifi()

    charger.requester.process_request = AsyncMock(
        return_value={"ok": True, "msg": "failed"}
    )
    with pytest.raises(UnknownError):
        await charger.restart_wifi()


async def test_client_restart_evse_errors():
    """Verify restart_evse error handling."""
    charger = OpenEVSE("openevse.test.tld")
    charger._config["version"] = "5.0.0"
    charger.requester = MagicMock()
    charger.requester.process_request = AsyncMock(return_value={"ok": False})
    with pytest.raises(UnknownError):
        await charger.restart_evse()


async def test_client_led_brightness_errors():
    """Verify set_led_brightness error handling."""
    charger = OpenEVSE("openevse.test.tld")
    charger._config["version"] = "4.1.0"
    charger.requester = MagicMock()
    charger.requester.process_request = AsyncMock(return_value={"ok": False})
    with pytest.raises(UnknownError):
        await charger.set_led_brightness(128)

    charger.requester.process_request = AsyncMock(
        return_value={"ok": True, "msg": "failed"}
    )
    with pytest.raises(UnknownError):
        await charger.set_led_brightness(128)


async def test_client_divert_mode_errors():
    """Verify set_divert_mode error handling."""
    charger = OpenEVSE("openevse.test.tld")
    charger.requester = MagicMock()
    charger.requester.process_request = AsyncMock(return_value={"ok": False})
    with pytest.raises(UnknownError):
        await charger.set_divert_mode("fast")


async def test_client_ws_start_active_tasks():
    """Verify ws_start behavior when tasks are already active."""
    charger = OpenEVSE("openevse.test.tld")
    charger._loop = asyncio.get_running_loop()
    charger.websocket = MagicMock()
    charger.websocket.listen = AsyncMock()
    charger.websocket.keepalive = AsyncMock()

    task = asyncio.create_task(asyncio.sleep(0.1))
    charger.tasks = [task]
    # Hits elif active_tasks: path
    await charger.ws_start()
    assert task.cancelled()
    assert len(charger.tasks) == 2  # listen and keepalive
    for t in charger.tasks:
        t.cancel()
    await asyncio.gather(*charger.tasks, return_exceptions=True)
    await asyncio.gather(task, return_exceptions=True)


async def test_client_shaper_active_coverage():
    """Verify shaper_active property with various data types and fallbacks."""
    charger = OpenEVSE("openevse.test.tld")

    # bool path (1044)
    charger._status = {"shaper": True}
    assert charger.shaper_active is True

    # int path (1046)
    charger._status = {"shaper": 1}
    assert charger.shaper_active is True

    # str path (1048)
    charger._status = {"shaper": "true"}
    assert charger.shaper_active is True
    charger._status = {"shaper": "1"}
    assert charger.shaper_active is True

    # fallback path (1049)
    charger._status = {"shaper": [123]}
    assert charger.shaper_active is True


async def test_client_lifecycle_branches():
    """Verify internal lifecycle branch handling."""
    charger = OpenEVSE("openevse.test.tld")
    charger._loop = asyncio.get_running_loop()
    charger.websocket = MagicMock()
    charger.websocket.listen = AsyncMock()
    charger.websocket.keepalive = AsyncMock()

    # Initialize tasks when none exist
    charger.tasks = None
    await charger.ws_start()
    assert len(charger.tasks) == 2
    for t in charger.tasks:
        t.cancel()
    await asyncio.gather(*charger.tasks, return_exceptions=True)


async def test_client_update_non_dict_response(test_charger, caplog):
    """Verify that update() handles non-dictionary responses gracefully."""
    # Mock self.process_request to return a string directly, bypassing Requester's dict-wrapping
    with patch.object(
        test_charger, "process_request", AsyncMock(return_value="Not a dictionary")
    ):
        with caplog.at_level(logging.WARNING):
            await test_charger.update(force_full=True)
    assert (
        "Unexpected non-dict response from http://openevse.test.tld/status: Not a dictionary"
        in caplog.text
    )


async def test_client_full_refresh_callbacks(test_charger, mock_aioclient, caplog):
    """Verify that full_refresh() executes user callbacks and handles exceptions."""
    # Mock data to allow update() to succeed
    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body='{"state": 1, "ok": True}',
        repeat=True,
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"version": "4.0.1", "ok": True}',
        repeat=True,
    )

    # 1. Test async callback
    async_cb = AsyncMock()
    test_charger.set_update_callback(async_cb)
    await test_charger.full_refresh()
    async_cb.assert_awaited_once()

    # 2. Test sync callback
    sync_cb = MagicMock()
    test_charger.set_update_callback(sync_cb)
    await test_charger.full_refresh()
    sync_cb.assert_called_once()

    # 3. Test callback exception
    error_cb = MagicMock(side_effect=Exception("Callback failed"))
    test_charger.set_update_callback(error_cb)
    with caplog.at_level(logging.ERROR):
        await test_charger.full_refresh()
    assert "Exception in user callback: Callback failed" in caplog.text


async def test_callback_serialization(test_charger, mock_aioclient):
    """Verify that concurrent callback triggers are serialized via the lock."""
    call_count = 0
    active_calls = 0
    max_concurrent_calls = 0

    async def slow_callback():
        nonlocal call_count, active_calls, max_concurrent_calls
        active_calls += 1
        max_concurrent_calls = max(max_concurrent_calls, active_calls)
        call_count += 1
        await asyncio.sleep(0.1)
        # Yield control to allow another task to attempt entry
        await asyncio.sleep(0)
        active_calls -= 1

    test_charger.set_update_callback(slow_callback)

    # Trigger via two paths in parallel: full_refresh and _invoke_callback
    mock_aioclient.get(
        "http://openevse.test.tld/status", status=200, body='{"status": "sleeping"}'
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config", status=200, body='{"firmware": "4.1.0"}'
    )

    await asyncio.gather(test_charger.full_refresh(), test_charger._invoke_callback())

    assert call_count == 2
    assert max_concurrent_calls == 1


@pytest.mark.asyncio
async def test_callback_reentrancy(test_charger):
    """Verify that re-entrant callback calls do not deadlock and are coalesced."""
    call_count = 0

    async def reentrant_callback():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Manually trigger another invocation while this one is running
            # This would have deadlocked before with the plain lock
            await test_charger._invoke_callback()

    test_charger.set_update_callback(reentrant_callback)

    await test_charger._invoke_callback()

    # Total calls should be 2: the original and the coalesced one
    assert call_count == 2
