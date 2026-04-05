"""Tests for property accessors."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from openevsehttp.__main__ import OpenEVSE
from openevsehttp.exceptions import UnsupportedFeature

pytestmark = pytest.mark.asyncio

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
SERVER_URL = "openevse.test.tld"


# ── status / state ──────────────────────────────────────────────────


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


async def test_get_status_unknown():
    """Test status property with unknown/invalid codes."""
    charger = OpenEVSE(SERVER_URL)
    # Unknown code
    charger._status = {"state": 99}
    assert charger.status == "unknown"

    # Invalid type
    charger._status = {"state": "invalid"}
    assert charger.status == "unknown"  # code 0 fallback


async def test_get_state_unknown():
    """Test state property with unknown/invalid codes."""
    charger = OpenEVSE(SERVER_URL)
    # Unknown code
    charger._status = {"state": 99}
    assert charger.state == "unknown"

    # Invalid type
    charger._status = {"state": "invalid"}
    assert charger.state == "unknown"  # code 0 fallback


# ── wifi / network ──────────────────────────────────────────────────


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
    "fixture, expected", [("test_charger", "1234567890AB"), ("test_charger_v2", None)]
)
async def test_wifi_serial(fixture, expected, request):
    """Test wifi_serial reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.wifi_serial
    assert status == expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "STA"), ("test_charger_v2", "STA")],
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


# ── firmware ────────────────────────────────────────────────────────


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
    "fixture, expected", [("test_charger", None), ("test_charger_v2", "4.0.1")]
)
async def test_get_protocol_version(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.protocol_version
    assert status == expected
    await charger.ws_disconnect()


# ── hardware config ─────────────────────────────────────────────────


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


# ── safety checks ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_tempt(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.temp_check_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", True)]
)
async def test_get_diodet(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.diode_check_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_ventt(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vent_required_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_groundt(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ground_check_enabled
    assert status is expected
    await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
async def test_get_relayt(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.stuck_relay_check_enabled
    assert status is expected
    await charger.ws_disconnect()


# ── trip counts ─────────────────────────────────────────────────────


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


# ── charging data ───────────────────────────────────────────────────


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
    "fixture, expected", [("test_charger", 240), ("test_charger_v2", 240)]
)
async def test_get_charging_voltage(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    try:
        await charger.update()
        status = charger.charging_voltage
        assert status == expected
    finally:
        await charger.ws_disconnect()


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", 7728), ("test_charger_v2", 0), ("test_charger_broken", None)],
)
async def test_get_charging_power(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    try:
        await charger.update()
        status = charger.charging_power
        assert status == expected
    finally:
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


# ── usage ───────────────────────────────────────────────────────────


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


async def test_usage_session_none():
    """Test usage_session returns None when no data is present."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {}
    assert charger.usage_session is None


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


# ── temperatures ────────────────────────────────────────────────────


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
    assert status == expected
    await charger.ws_disconnect()


async def test_ir_temperature():
    """Test ir_temperature property."""
    charger = OpenEVSE(SERVER_URL)
    charger._status = {"temp3": 250}
    assert charger.ir_temperature == 25.0


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


# ── time ────────────────────────────────────────────────────────────


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
    if not isinstance(bad_value, int | float):
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


async def test_async_charge_current_exception(test_charger):
    """Test get_charge_current exception path."""
    with patch.object(test_charger, "list_claims", side_effect=UnsupportedFeature):
        # Should catch UnsupportedFeature and return config/status fallback
        test_charger._config["max_current_soft"] = 32
        assert await test_charger.get_charge_current() == 32


# ── divert ──────────────────────────────────────────────────────────


async def test_async_charge_current_numeric_error(test_charger):
    """Test get_charge_current with malformed numeric data."""
    # Test TypeError in int conversion
    claims = {"properties": {"charge_current": "invalid"}}
    with patch.object(test_charger, "list_claims", return_value=claims):
        test_charger._config["max_current_soft"] = 24
        assert await test_charger.get_charge_current() == 24


async def test_get_override_state_non_dict(test_charger_new):
    """Test get_override_state handles non-dictionary responses."""
    with patch.object(test_charger_new, "get_override", return_value="string"):
        assert await test_charger_new.get_override_state() == "auto"


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


# ── override / manual override ──────────────────────────────────────


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


# ── vehicle ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("fixture, expected", [("test_charger", 1)])
async def test_get_vehicle(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.vehicle
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


# ── shaper ──────────────────────────────────────────────────────────


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


# ── limit / OTA ─────────────────────────────────────────────────────


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
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
async def test_get_ota_update(fixture, expected, request):
    """Test v4 Status reply."""
    charger = request.getfixturevalue(fixture)
    await charger.update()
    status = charger.ota_update
    assert status == expected
    await charger.ws_disconnect()


# ── MQTT ────────────────────────────────────────────────────────────


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


# ── emoncms / ocpp / uptime / freeram ───────────────────────────────


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


# ── power (current_power) ──────────────────────────────────────────


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


# ── missing data ────────────────────────────────────────────────────


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
