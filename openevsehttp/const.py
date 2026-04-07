"""Constants for the OpenEVSE HTTP python library."""

USER_AGENT = "python-openevse-http"
MIN_AMPS = 6
MAX_AMPS = 48

ERROR_TIMEOUT = "Timeout while updating"
INFO_LOOP_RUNNING = "Event loop already running, not creating new one."
UPDATE_TRIGGERS = [
    "config_version",
    "claims_version",
    "override_version",
    "schedule_version",
    "schedule_plan_version",
    "limit_version",
]

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

states = {
    0: "unknown",
    1: "not connected",
    2: "connected",
    3: "charging",
    4: "vent required",
    5: "diode check failed",
    6: "gfci fault",
    7: "no ground",
    8: "stuck relay",
    9: "gfci self-test failure",
    10: "over temperature",
    254: "sleeping",
    255: "disabled",
}

divert_mode = {
    "fast": 1,
    "eco": 2,
}

RAPI_ERRORS = [
    "RAPI_RESPONSE_QUEUE_FULL",
    "RAPI_RESPONSE_BUFFER_OVERFLOW",
    "RAPI_RESPONSE_TIMEOUT",
    "RAPI_RESPONSE_INVALID_RESPONSE",
    "RAPI_RESPONSE_CMD_TOO_LONG",
    "RAPI_RESPONSE_NOT_FOUND",
    "RAPI_RESPONSE_BLOCKED",
    "RAPI_RESPONSE_INVALID_COMMAND",
]
