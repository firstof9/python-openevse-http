"""Constants for the OpenEVSE HTTP python library."""

USER_AGENT = "python-openevse-http"
MIN_AMPS = 6
MAX_AMPS = 48

SOLAR = "solar"
GRID = "grid_ie"
BAT_LVL = "battery_level"
BAT_RANGE = "battery_range"
TTF = "time_to_full_charge"
VOLTAGE = "voltage"
SHAPER_LIVE = "shaper_live_pwr"
TYPE = "type"
VALUE = "value"
RELEASE = "release"
# https://github.com/OpenEVSE/openevse_esp32_firmware/blob/master/src/evse_man.h#L28
CLIENT = 20
