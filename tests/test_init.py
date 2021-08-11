def test_get_status(test_charger):
    """Test v4 Status reply"""
    status = test_charger.status
    assert status == "sleeping"


def test_get_ssid(test_charger):
    """Test v4 Status reply"""
    status = test_charger.wifi_ssid
    assert status == "Datanode-IoT"


def test_get_firmware(test_charger):
    """Test v4 Status reply"""
    status = test_charger.openevse_firmware
    assert status == "7.1.3"


def test_get_hostname(test_charger):
    """Test v4 Status reply"""
    status = test_charger.hostname
    assert status == "openevse-7b2c"


def test_get_ammeter_offset(test_charger):
    """Test v4 Status reply"""
    status = test_charger.ammeter_offset
    assert status == 0


def test_get_ammeter_scale_factor(test_charger):
    """Test v4 Status reply"""
    status = test_charger.ammeter_scale_factor
    assert status == 220


# Checks don't seem to be working
# def test_get_temp_check_enabled(test_charger):
#     """Test v4 Status reply"""
#     status = test_charger.temp_check_enabled
#     assert status


def test_get_service_level(test_charger):
    """Test v4 Status reply"""
    status = test_charger.service_level
    assert status == 2


def test_get_wifi_firmware(test_charger):
    """Test v4 Status reply"""
    status = test_charger.wifi_firmware
    assert status == "4.0.0"


def test_get_ip_address(test_charger):
    """Test v4 Status reply"""
    status = test_charger.ip_address
    assert status == "192.168.21.10"


def test_get_charging_voltage(test_charger):
    """Test v4 Status reply"""
    status = test_charger.charging_voltage
    assert status == 240


def test_get_mode(test_charger):
    """Test v4 Status reply"""
    status = test_charger.mode
    assert status == "STA"


def test_get_using_ethernet(test_charger):
    """Test v4 Status reply"""
    status = test_charger.using_ethernet
    assert not status


def test_get_stuck_relay_trip_count(test_charger):
    """Test v4 Status reply"""
    status = test_charger.stuck_relay_trip_count
    assert status == 0


def test_get_no_gnd_trip_count(test_charger):
    """Test v4 Status reply"""
    status = test_charger.no_gnd_trip_count
    assert status == 0


def test_get_gfi_trip_count(test_charger):
    """Test v4 Status reply"""
    status = test_charger.gfi_trip_count
    assert status == 1


def test_get_charge_time_elapsed(test_charger):
    """Test v4 Status reply"""
    status = test_charger.charge_time_elapsed
    assert status == 246


def test_get_wifi_signal(test_charger):
    """Test v4 Status reply"""
    status = test_charger.wifi_signal
    assert status == -61


def test_get_charging_current(test_charger):
    """Test v4 Status reply"""
    status = test_charger.charging_current
    assert status == 0


def test_get_current_capacity(test_charger):
    """Test v4 Status reply"""
    status = test_charger.current_capacity
    assert status == 48


def test_get_usage_total(test_charger):
    """Test v4 Status reply"""
    status = test_charger.usage_total
    assert status == 64582


def test_get_ambient_temperature(test_charger):
    """Test v4 Status reply"""
    status = test_charger.ambient_temperature
    assert status == 50.3


def test_get_rtc_temperature(test_charger):
    """Test v4 Status reply"""
    status = test_charger.rtc_temperature
    assert status == 50.3


def test_get_ir_temperature(test_charger):
    """Test v4 Status reply"""
    status = test_charger.ir_temperature
    assert status is None


def test_get_esp_temperature(test_charger):
    """Test v4 Status reply"""
    status = test_charger.esp_temperature
    assert status == 56.0


def test_get_time(test_charger):
    """Test v4 Status reply"""
    status = test_charger.time
    assert status == "2021-08-10T23:00:11Z"


def test_get_usage_session(test_charger):
    """Test v4 Status reply"""
    status = test_charger.usage_session
    assert status == 275.71


def test_get_protocol_version(test_charger):
    """Test v4 Status reply"""
    status = test_charger.protocol_version
    assert status == "-"


def test_get_min_amps(test_charger):
    """Test v4 Status reply"""
    status = test_charger.min_amps
    assert status == 6


def test_get_max_amps(test_charger):
    """Test v4 Status reply"""
    status = test_charger.max_amps
    assert status == 48
