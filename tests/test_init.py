import pytest
import openevsehttp


def test_get_status_auth(test_charger_auth):
    """Test v4 Status reply"""
    test_charger_auth.update()
    status = test_charger_auth.status
    assert status == "sleeping"


def test_get_status_auth_err(test_charger_auth_err):
    """Test v4 Status reply"""
    with pytest.raises(openevsehttp.AuthenticationError):
        test_charger_auth_err.update()
        assert test_charger_auth_err is None


def test_send_command(test_charger, send_command_mock):
    """Test v4 Status reply"""
    status = test_charger.send_command("test")
    assert status == (True, "test")


def test_send_command_missing(test_charger, send_command_mock_missing):
    """Test v4 Status reply"""
    status = test_charger.send_command("test")
    assert status == (False, "")


def test_send_command_auth(test_charger_auth, send_command_mock):
    """Test v4 Status reply"""
    status = test_charger_auth.send_command("test")
    assert status == (True, "test")


def test_send_command_parse_err(test_charger_auth, send_command_parse_err):
    """Test v4 Status reply"""
    with pytest.raises(openevsehttp.ParseJSONError):
        status = test_charger_auth.send_command("test")
        assert status is None


def test_send_command_auth_err(test_charger_auth, send_command_auth_err):
    """Test v4 Status reply"""
    with pytest.raises(openevsehttp.AuthenticationError):
        status = test_charger_auth.send_command("test")
        assert status is None


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "sleeping"), ("test_charger_v2", "not connected")],
)
def test_get_status(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.status
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "Datanode-IoT"), ("test_charger_v2", "nsavanup_IoT")],
)
def test_get_ssid(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.wifi_ssid
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "7.1.3"), ("test_charger_v2", "5.0.1")]
)
def test_get_firmware(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.openevse_firmware
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "openevse-7b2c"), ("test_charger_v2", "openevse")],
)
def test_get_hostname(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.hostname
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
def test_get_ammeter_offset(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.ammeter_offset
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 220), ("test_charger_v2", 220)]
)
def test_get_ammeter_scale_factor(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.ammeter_scale_factor
    assert status == expected


# Checks don't seem to be working
# def test_get_temp_check_enabled(fixture, expected, request):
#     """Test v4 Status reply"""
#     status = fixture, expected, request.temp_check_enabled
#     assert status


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 2), ("test_charger_v2", 2)]
)
def test_get_service_level(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.service_level
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "4.0.0"), ("test_charger_v2", "2.9.1")]
)
def test_get_wifi_firmware(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.wifi_firmware
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "192.168.21.10"), ("test_charger_v2", "192.168.1.67")],
)
def test_get_ip_address(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.ip_address
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 240), ("test_charger_v2", 240)]
)
def test_get_charging_voltage(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.charging_voltage
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "STA"), ("test_charger_v2", "STA")]
)
def test_get_mode(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.mode
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", False), ("test_charger_v2", False)]
)
def test_get_using_ethernet(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.using_ethernet
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
def test_get_stuck_relay_trip_count(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.stuck_relay_trip_count
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
def test_get_no_gnd_trip_count(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.no_gnd_trip_count
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 1), ("test_charger_v2", 0)]
)
def test_get_gfi_trip_count(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.gfi_trip_count
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 246), ("test_charger_v2", 8751)]
)
def test_get_charge_time_elapsed(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.charge_time_elapsed
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", -61), ("test_charger_v2", -56)]
)
def test_get_wifi_signal(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.wifi_signal
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 0), ("test_charger_v2", 0)]
)
def test_get_charging_current(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.charging_current
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 25)]
)
def test_get_current_capacity(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.current_capacity
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 64582), ("test_charger_v2", 1585443)]
)
def test_get_usage_total(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.usage_total
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 50.3), ("test_charger_v2", 34.0)]
)
def test_get_ambient_temperature(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.ambient_temperature
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 50.3), ("test_charger_v2", 0.0)]
)
def test_get_rtc_temperature(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.rtc_temperature
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", None), ("test_charger_v2", None)]
)
def test_get_ir_temperature(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.ir_temperature
    assert status is None


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 56.0), ("test_charger_v2", None)]
)
def test_get_esp_temperature(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.esp_temperature
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected",
    [("test_charger", "2021-08-10T23:00:11Z"), ("test_charger_v2", None)],
)
def test_get_time(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.time
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 275.71), ("test_charger_v2", 7003.41)]
)
def test_get_usage_session(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.usage_session
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", "-"), ("test_charger_v2", "4.0.1")]
)
def test_get_protocol_version(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.protocol_version
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 6), ("test_charger_v2", 6)]
)
def test_get_min_amps(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.min_amps
    assert status == expected


@pytest.mark.parametrize(
    "fixture, expected", [("test_charger", 48), ("test_charger_v2", 48)]
)
def test_get_max_amps(fixture, expected, request):
    """Test v4 Status reply"""
    charger = request.getfixturevalue(fixture)
    charger.update()
    status = charger.max_amps
    assert status == expected
