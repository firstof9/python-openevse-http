"""Tests for property accessors."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from openevsehttp import OpenEVSE
from openevsehttp.exceptions import UnsupportedFeature
from tests.conftest import MockClientSession

pytestmark = pytest.mark.asyncio

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
SERVER_URL = "openevse.test.tld"


@pytest.mark.parametrize(
    "fixture, prop, expected",
    [
        # status / state
        ("test_charger", "status", "sleeping"),
        ("test_charger_v2", "status", "not connected"),
        ("test_charger", "state", "sleeping"),
        ("test_charger_v2", "state", "not connected"),
        ("test_charger", "state_raw", 254),
        ("test_charger_v2", "state_raw", 1),
        # wifi / network
        ("test_charger", "wifi_ssid", "Datanode-IoT"),
        ("test_charger_v2", "wifi_ssid", "nsavanup_IoT"),
        ("test_charger", "hostname", "openevse-7b2c"),
        ("test_charger_v2", "hostname", "openevse"),
        ("test_charger", "ip_address", "192.168.21.10"),
        ("test_charger_v2", "ip_address", "192.168.1.67"),
        ("test_charger", "wifi_signal", -61),
        ("test_charger_v2", "wifi_signal", -56),
        ("test_charger", "wifi_serial", "1234567890AB"),
        ("test_charger_v2", "wifi_serial", None),
        ("test_charger", "mode", "STA"),
        ("test_charger_v2", "mode", "STA"),
        ("test_charger", "using_ethernet", False),
        ("test_charger_v2", "using_ethernet", False),
        # firmware
        ("test_charger", "openevse_firmware", "7.1.3"),
        ("test_charger_v2", "openevse_firmware", "5.0.1"),
        ("test_charger", "wifi_firmware", "4.1.2"),
        ("test_charger_v2", "wifi_firmware", "2.9.1"),
        ("test_charger_dev", "wifi_firmware", "4.1.5"),
        ("test_charger_broken_semver", "wifi_firmware", "master_abcd123"),
        ("test_charger", "protocol_version", None),
        ("test_charger_v2", "protocol_version", "4.0.1"),
        # hardware config
        ("test_charger", "ammeter_offset", 0),
        ("test_charger_v2", "ammeter_offset", 0),
        ("test_charger", "ammeter_scale_factor", 220),
        ("test_charger_v2", "ammeter_scale_factor", 220),
        ("test_charger", "service_level", "2"),
        ("test_charger_v2", "service_level", "2"),
        # safety checks
        ("test_charger", "temp_check_enabled", False),
        ("test_charger_v2", "temp_check_enabled", False),
        ("test_charger", "diode_check_enabled", False),
        ("test_charger_v2", "diode_check_enabled", True),
        ("test_charger", "vent_required_enabled", False),
        ("test_charger_v2", "vent_required_enabled", False),
        ("test_charger", "ground_check_enabled", False),
        ("test_charger_v2", "ground_check_enabled", False),
        ("test_charger", "stuck_relay_check_enabled", False),
        ("test_charger_v2", "stuck_relay_check_enabled", False),
        # trip counts
        ("test_charger", "stuck_relay_trip_count", 0),
        ("test_charger_v2", "stuck_relay_trip_count", 0),
        ("test_charger", "no_gnd_trip_count", 0),
        ("test_charger_v2", "no_gnd_trip_count", 0),
        ("test_charger", "gfi_trip_count", 1),
        ("test_charger_v2", "gfi_trip_count", 0),
        (
            "test_charger_new",
            "checks_count",
            {"gfcicount": 1, "nogndcount": 0, "stuckcount": 0},
        ),
        (
            "test_charger_v2",
            "checks_count",
            {"gfcicount": 0, "nogndcount": 0, "stuckcount": 0},
        ),
        # charging data
        ("test_charger", "charge_time_elapsed", 246),
        ("test_charger_v2", "charge_time_elapsed", 8751),
        ("test_charger", "charging_current", 32.2),
        ("test_charger_v2", "charging_current", 0),
        ("test_charger", "current_capacity", 48),
        ("test_charger_v2", "current_capacity", 25),
        ("test_charger", "charging_voltage", 240),
        ("test_charger_v2", "charging_voltage", 240),
        ("test_charger", "charging_power", 7728),
        ("test_charger_v2", "charging_power", 0),
        ("test_charger_broken", "charging_power", None),
        ("test_charger", "charge_rate", 0),
        ("test_charger_v2", "charge_rate", 0),
        ("test_charger", "available_current", None),
        ("test_charger_v2", "available_current", None),
        ("test_charger", "smoothed_available_current", None),
        ("test_charger_v2", "smoothed_available_current", None),
        ("test_charger", "min_amps", 6),
        ("test_charger_v2", "min_amps", 6),
        ("test_charger", "max_amps", 48),
        ("test_charger_v2", "max_amps", 48),
        ("test_charger", "max_current_soft", 48),
        ("test_charger_v2", "max_current_soft", 25),
        ("test_charger_new", "max_current", 48),
        ("test_charger_v2", "max_current", None),
        # usage
        ("test_charger", "usage_total", 64582),
        ("test_charger_v2", "usage_total", 1585443),
        ("test_charger_new", "usage_total", 20127.22817),
        ("test_charger", "usage_session", 275.71),
        ("test_charger_v2", "usage_session", 7003.41),
        ("test_charger_new", "usage_session", 0),
        ("test_charger", "total_day", None),
        ("test_charger_v2", "total_day", None),
        ("test_charger_new", "total_day", 0),
        ("test_charger", "total_week", None),
        ("test_charger_v2", "total_week", None),
        ("test_charger_new", "total_week", 1.567628635),
        ("test_charger", "total_month", None),
        ("test_charger_v2", "total_month", None),
        ("test_charger_new", "total_month", 37.21857071),
        ("test_charger", "total_year", None),
        ("test_charger_v2", "total_year", None),
        ("test_charger_new", "total_year", 2155.219982),
        # temperatures
        ("test_charger", "ambient_temperature", 50.3),
        ("test_charger_v2", "ambient_temperature", 34.0),
        ("test_charger", "rtc_temperature", 50.3),
        ("test_charger_v2", "rtc_temperature", None),
        ("test_charger", "ir_temperature", None),
        ("test_charger_v2", "ir_temperature", None),
        ("test_charger", "esp_temperature", 56.0),
        ("test_charger_v2", "esp_temperature", None),
        # divert
        ("test_charger", "divert_active", True),
        ("test_charger_v2", "divert_active", False),
        ("test_charger_new", "divert_active", False),
        ("test_charger", "divertmode", "eco"),
        ("test_charger_v2", "divertmode", "fast"),
        ("test_charger_broken", "divertmode", "eco"),
        ("test_charger_new", "divertmode", "fast"),
        ("test_charger", "charge_mode", "fast"),
        ("test_charger_v2", "charge_mode", "fast"),
        # override / manual override
        ("test_charger", "manual_override", False),
        ("test_charger_v2", "manual_override", False),
        # vehicle
        ("test_charger", "vehicle", 1),
        ("test_charger", "vehicle_soc", 75),
        ("test_charger_v2", "vehicle_soc", None),
        ("test_charger", "vehicle_range", 468),
        ("test_charger_v2", "vehicle_range", None),
        # shaper
        ("test_charger", "shaper_active", True),
        ("test_charger_v2", "shaper_active", None),
        ("test_charger", "shaper_live_power", 2299),
        ("test_charger_v2", "shaper_live_power", None),
        ("test_charger", "shaper_available_current", 21),
        ("test_charger_v2", "shaper_available_current", None),
        ("test_charger_broken", "shaper_available_current", 48),
        ("test_charger", "shaper_max_power", 4000),
        ("test_charger_v2", "shaper_max_power", None),
        ("test_charger", "shaper_updated", False),
        ("test_charger_v2", "shaper_updated", False),
        ("test_charger_broken", "shaper_updated", False),
        ("test_charger_new", "shaper_updated", True),
        # limit / OTA
        ("test_charger", "has_limit", None),
        ("test_charger_v2", "has_limit", None),
        ("test_charger_new", "has_limit", False),
        ("test_charger", "ota_update", False),
        ("test_charger_v2", "ota_update", False),
        # MQTT
        ("test_charger", "mqtt_connected", True),
        ("test_charger_v2", "mqtt_connected", False),
        ("test_charger_broken", "mqtt_connected", False),
        # emoncms / ocpp / uptime / freeram
        ("test_charger_new", "emoncms_connected", 0),
        ("test_charger_v2", "emoncms_connected", 0),
        ("test_charger_new", "ocpp_connected", 0),
        ("test_charger_v2", "ocpp_connected", None),
        ("test_charger_new", "uptime", 1208725),
        ("test_charger_v2", "uptime", None),
        ("test_charger_new", "freeram", 167436),
        ("test_charger_v2", "freeram", None),
        # power (current_power)
        ("test_charger", "current_power", UnsupportedFeature),
        ("test_charger_v2", "current_power", UnsupportedFeature),
        ("test_charger_broken", "current_power", UnsupportedFeature),
        ("test_charger_new", "current_power", 4500),
    ],
)
async def test_simple_properties(fixture, prop, expected, request):
    """Test simple property accessors."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            _ = getattr(charger, prop)
    else:
        assert getattr(charger, prop) == expected
    await charger.ws_disconnect()


async def test_get_status_unknown():
    """Test status property with unknown/invalid codes."""
    charger = OpenEVSE(SERVER_URL, session=object())
    # Unknown code
    charger._status = {"state": 99}
    assert charger.status == "unknown"

    # Invalid type
    charger._status = {"state": "invalid"}
    assert charger.status == "unknown"  # code 0 fallback


async def test_get_state_unknown():
    """Test state property with unknown/invalid codes."""
    charger = OpenEVSE(SERVER_URL, session=object())
    # Unknown code
    charger._status = {"state": 99}
    assert charger.state == "unknown"

    # Invalid type
    charger._status = {"state": "invalid"}
    assert charger.state == "unknown"  # code 0 fallback


async def test_charging_power_non_numeric():
    """Test charging_power with non-numeric values."""
    charger = OpenEVSE("openevse.test.tld")
    charger._status = {"voltage": "240", "amp": 32}
    assert charger.charging_power is None
    charger._status = {"voltage": 240, "amp": "32"}
    assert charger.charging_power is None


async def test_usage_session_none():
    """Test usage_session returns None when no data is present."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {}
    assert charger.usage_session is None


async def test_get_ambient_temperature_zero():
    """Test ambient_temperature property with 0°C."""
    charger = OpenEVSE(SERVER_URL)
    # 0 should be 0.0
    charger._status = {"temp": 0}
    assert charger.ambient_temperature == 0.0

    # Fallback to temp1
    charger._status = {"temp": None, "temp1": 0}
    assert charger.ambient_temperature == 0.0


async def test_get_ambient_temperature_none():
    """Test ambient_temperature property with missing sensors."""
    charger = OpenEVSE(SERVER_URL)
    # Both missing
    charger._status = {"temp": None, "temp1": None}
    assert charger.ambient_temperature is None

    # Both missing in key sense
    charger._status = {}
    assert charger.ambient_temperature is None


async def test_ir_temperature():
    """Test ir_temperature property."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {"temp3": 250}
    assert charger.ir_temperature == 25.0


@pytest.mark.parametrize(
    "fixture, expected_str",
    [("test_charger", "2021-08-10T23:00:11Z"), ("test_charger_v2", None)],
)
async def test_get_time(fixture, expected_str, request):
    """Test time property."""
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
    "fixture", ["test_charger", "test_charger_v2", "test_charger_new"]
)
@pytest.mark.parametrize(
    "bad_value",
    [
        "not-a-timestamp",
        123456789,
        True,
        {"some": "dict"},
    ],
)
async def test_time_parsing_errors(request, fixture, bad_value):
    """Test that ValueError and AttributeError are caught and return None."""
    charger = request.getfixturevalue(fixture)
    charger._status["time"] = bad_value
    result = charger.time
    assert result is None

    # Test vehicle_eta with non-numeric value (only if not already numeric)
    if type(bad_value) not in (int, float):
        charger._status["vehicle_eta"] = bad_value
        result = charger.vehicle_eta
        assert result is None


async def test_status_logic_coverage(test_charger):
    """Test status logic coverage for fallback and positive cases."""
    # Positive case: status string exists
    test_charger._status["status"] = "charging"
    assert test_charger.status == "charging"

    # Fallback Case: status is None
    test_charger._status["status"] = None
    assert test_charger.status == test_charger.state

    # Fallback Case: status is missing
    del test_charger._status["status"]
    assert test_charger.status == test_charger.state
    await test_charger.ws_disconnect()


async def test_async_charge_current_exception(test_charger):
    """Test get_charge_current exception path."""
    with patch.object(test_charger, "list_claims", side_effect=UnsupportedFeature):
        # Should catch UnsupportedFeature and return config/status fallback
        test_charger._config["max_current_soft"] = 32
        assert await test_charger.get_charge_current() == 32
    await test_charger.ws_disconnect()


async def test_async_charge_current_numeric_error(test_charger):
    """Test get_charge_current with malformed numeric data."""
    # Test TypeError in int conversion
    claims = {"properties": {"charge_current": "invalid"}}
    with patch.object(test_charger, "list_claims", return_value=claims):
        test_charger._config["max_current_soft"] = 24
        assert await test_charger.get_charge_current() == 24
    await test_charger.ws_disconnect()


async def test_get_override_state_non_dict(test_charger_new):
    """Test get_override_state handles non-dictionary responses."""
    with patch.object(test_charger_new, "get_override", return_value="string"):
        assert await test_charger_new.get_override_state() == "auto"
    await test_charger_new.ws_disconnect()


async def test_get_override_state_null_handling(test_charger_new):
    """Test get_override_state handles None (null in JSON)."""
    # Mock get_override to return a dict with state=None
    with patch.object(test_charger_new, "get_override", return_value={"state": None}):
        assert await test_charger_new.get_override_state() == "auto"

    # Mock get_override to return a dict with state="active"
    with patch.object(
        test_charger_new, "get_override", return_value={"state": "active"}
    ):
        assert await test_charger_new.get_override_state() == "active"
    await test_charger_new.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected_seconds",
    [("test_charger", 18000), ("test_charger_v2", None)],
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


async def test_ota_properties():
    """Test ota_progress and ota_state properties."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {"ota_update": 1, "ota_progress": 45, "ota": "started"}
    assert charger.ota_update is True
    assert charger.ota_progress == 45
    assert charger.ota_state == "started"

    charger._status = {"ota_update": 0}
    assert charger.ota_update is False
    assert charger.ota_progress is None
    assert charger.ota_state is None


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

    charger = OpenEVSE(SERVER_URL, session=MockClientSession(mock_aioclient))
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


async def test_sensor_numeric_errors():
    """Test all temperature/usage accessors handle non-numeric data."""
    charger = OpenEVSE(SERVER_URL)
    # temp and temp1 are used for ambient_temperature
    charger._status = {"temp": "fail", "temp1": "fail"}
    assert charger.ambient_temperature is None

    # temp2, temp3, temp4
    charger._status = {"temp2": "fail", "temp3": "fail", "temp4": "fail"}
    assert charger.rtc_temperature is None
    assert charger.ir_temperature is None
    assert charger.esp_temperature is None

    # wattsec for usage_session
    charger._status = {"wattsec": "fail"}
    assert charger.usage_session is None


async def test_config_boolean_coercion():
    """Test boolean properties reading from config handle non-numeric data."""
    charger = OpenEVSE(SERVER_URL)
    # Test with None values (which return False via bool() coercion)
    charger._config = {"ventt": None, "groundt": None, "relayt": None}
    assert charger.vent_required_enabled is False
    assert charger.ground_check_enabled is False
    assert charger.stuck_relay_check_enabled is False

    # Test with string values that are truthy
    charger._config = {"ventt": "1", "groundt": "true", "relayt": "yes"}
    assert charger.vent_required_enabled is True
    assert charger.ground_check_enabled is True
    assert charger.stuck_relay_check_enabled is True


async def test_wifi_firmware_none():
    """Test wifi_firmware returns None when version is missing."""
    charger = OpenEVSE(SERVER_URL)
    charger._config = {}
    assert charger.wifi_firmware is None
