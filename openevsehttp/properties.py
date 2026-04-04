"""Property accessors for the OpenEVSE charger."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .const import MAX_AMPS, MIN_AMPS, states
from .exceptions import UnsupportedFeature

_LOGGER = logging.getLogger(__name__)


class PropertiesMixin:
    """Mixin providing all @property accessors for OpenEVSE."""

    _status: dict
    _config: dict

    # These are used by properties but defined in client.py
    def _version_check(self, min_version: str, max_version: str = "") -> bool:
        raise NotImplementedError

    async def list_claims(self, target: bool | None = None) -> Any:
        raise NotImplementedError

    async def get_override(self) -> dict[str, str] | dict[str, Any]:
        raise NotImplementedError

    @property
    def led_brightness(self) -> int | None:
        """Return charger led_brightness."""
        if not self._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        return self._config.get("led_brightness")

    @property
    def hostname(self) -> str | None:
        """Return charger hostname."""
        return self._config.get("hostname")

    @property
    def wifi_ssid(self) -> str | None:
        """Return charger connected SSID."""
        return self._config.get("ssid")

    @property
    def ammeter_offset(self) -> int | None:
        """Return ammeter's current offset."""
        return self._config.get("offset")

    @property
    def ammeter_scale_factor(self) -> int | None:
        """Return ammeter's current scale factor."""
        return self._config.get("scale")

    @property
    def temp_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("tempt", False))

    @property
    def diode_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("diodet", False))

    @property
    def vent_required_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("ventt", False))

    @property
    def ground_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("groundt", False))

    @property
    def stuck_relay_check_enabled(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._config.get("relayt", False))

    @property
    def service_level(self) -> str | None:
        """Return the service level."""
        return self._config.get("service")

    @property
    def openevse_firmware(self) -> str | None:
        """Return the firmware version."""
        return self._config.get("firmware")

    @property
    def max_current_soft(self) -> int | None:
        """Return the max current soft."""
        if "max_current_soft" in self._config:
            return self._config.get("max_current_soft")
        return self._status.get("pilot")

    @property
    async def async_charge_current(self) -> int | None:
        """Return the charge current."""
        try:
            claims = await self.list_claims(target=True)
            # Normalize list to find an element with properties or use the first one
            if isinstance(claims, list):
                claims = next(
                    (c for c in claims if isinstance(c, dict) and "properties" in c),
                    claims[0] if claims else {},
                )

            if isinstance(claims, dict):
                properties = claims.get("properties", {})
                if "charge_current" in properties:
                    try:
                        charge_current = int(properties["charge_current"])
                        max_hard = int(self._config.get("max_current_hard", 48))
                        return min(charge_current, max_hard)
                    except (TypeError, ValueError):
                        pass
        except (UnsupportedFeature, IndexError, KeyError):
            pass

        if "max_current_soft" in self._config:
            return self._config.get("max_current_soft")
        return self._status.get("pilot")

    @property
    def max_current(self) -> int | None:
        """Return the max current."""
        return self._status.get("max_current", None)

    @property
    def wifi_firmware(self) -> str | None:
        """Return the ESP firmware version."""
        value = self._config.get("version")
        if value is not None and "dev" in value:
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
        return value

    @property
    def ip_address(self) -> str | None:
        """Return the ip address."""
        return self._status.get("ipaddress")

    @property
    def charging_voltage(self) -> int | None:
        """Return the charging voltage."""
        return self._status.get("voltage")

    @property
    def mode(self) -> str | None:
        """Return the mode."""
        return self._status.get("mode")

    @property
    def using_ethernet(self) -> bool:
        """Return True if enabled, False if disabled."""
        return bool(self._status.get("eth_connected", False))

    @property
    def stuck_relay_trip_count(self) -> int | None:
        """Return the stuck relay count."""
        return self._status.get("stuckcount")

    @property
    def no_gnd_trip_count(self) -> int | None:
        """Return the no ground count."""
        return self._status.get("nogndcount")

    @property
    def gfi_trip_count(self) -> int | None:
        """Return the GFCI count."""
        return self._status.get("gfcicount")

    @property
    def status(self) -> str:
        """Return charger's state."""
        # Check if "status" is already a non-null string in _status (some versions)
        val = self._status.get("status")
        if val is not None:
            return str(val)

        # Fall back to state mapping
        return self.state

    @property
    def state(self) -> str:
        """Return charger's state."""
        try:
            code = int(self._status.get("state", 0))
        except (ValueError, TypeError):
            code = 0
        return states.get(code, "unknown")

    @property
    def state_raw(self) -> int | None:
        """Return charger's state int form."""
        return self._status.get("state")

    @property
    def charge_time_elapsed(self) -> int | None:
        """Return elapsed charging time."""
        return self._status.get("elapsed")

    @property
    def wifi_signal(self) -> str | None:
        """Return charger's wifi signal."""
        return self._status.get("srssi")

    @property
    def charging_current(self) -> float | None:
        """Return the charge current.

        0 if is not currently charging.
        """
        return self._status.get("amp")

    @property
    def current_capacity(self) -> int | None:
        """Return the current capacity."""
        return self._status.get("pilot")

    @property
    def usage_total(self) -> float | None:
        """Return the total energy usage in Wh."""
        if "total_energy" in self._status:
            return self._status.get("total_energy")
        return self._status.get("watthour")

    @property
    def ambient_temperature(self) -> float | None:
        """Return the temperature of the ambient sensor, in degrees Celsius."""
        temp = self._status.get("temp")
        if temp is not None:
            return temp / 10

        temp1 = self._status.get("temp1")
        if temp1 is not None:
            return temp1 / 10

        return None

    @property
    def rtc_temperature(self) -> float | None:
        """Return the temperature of the real time clock sensor."""
        temp = self._status.get("temp2")
        if temp is None or isinstance(temp, bool):
            return None
        return float(temp) / 10

    @property
    def ir_temperature(self) -> float | None:
        """Return the temperature of the IR remote sensor.

        In degrees Celsius.
        """
        temp = self._status.get("temp3")
        if temp is None or isinstance(temp, bool):
            return None
        return float(temp) / 10

    @property
    def esp_temperature(self) -> float | None:
        """Return the temperature of the ESP sensor, in degrees Celsius."""
        temp = self._status.get("temp4")
        if temp is None or isinstance(temp, bool):
            return None
        return float(temp) / 10

    @property
    def time(self) -> datetime | None:
        """Get the RTC time."""
        value = self._status.get("time")
        if value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        return None

    @property
    def usage_session(self) -> float | None:
        """Get the energy usage for the current charging session.

        Return the energy usage in Wh.
        """
        if "session_energy" in self._status:
            return self._status.get("session_energy")
        wattsec = self._status.get("wattsec")
        if wattsec is not None:
            return float(round(wattsec / 3600, 2))
        return None

    @property
    def total_day(self) -> float | None:
        """Get the total day energy usage."""
        return self._status.get("total_day", None)

    @property
    def total_week(self) -> float | None:
        """Get the total week energy usage."""
        return self._status.get("total_week", None)

    @property
    def total_month(self) -> float | None:
        """Get the total week energy usage."""
        return self._status.get("total_month", None)

    @property
    def total_year(self) -> float | None:
        """Get the total year energy usage."""
        return self._status.get("total_year", None)

    @property
    def has_limit(self) -> bool | None:
        """Return if a limit has been set."""
        return self._status.get("has_limit", self._status.get("limit", None))

    @property
    def protocol_version(self) -> str | None:
        """Return the protocol version."""
        protocol = self._config.get("protocol")
        if protocol == "-":
            return None
        return protocol

    @property
    def vehicle(self) -> bool:
        """Return if a vehicle is connected dto the EVSE."""
        return self._status.get("vehicle", False)

    @property
    def ota_update(self) -> bool:
        """Return if an OTA update is active."""
        return self._status.get("ota_update", False)

    @property
    def manual_override(self) -> bool:
        """Return if Manual Override is set."""
        return self._status.get("manual_override", False)

    @property
    def divertmode(self) -> str:
        """Return the divert mode."""
        mode = self._status.get("divertmode", 1)
        if mode == 1:
            return "fast"
        return "eco"

    @property
    def charge_mode(self) -> str | None:
        """Return the charge mode."""
        return self._config.get("charge_mode")

    @property
    def available_current(self) -> float | None:
        """Return the computed available current for divert."""
        return self._status.get("available_current")

    @property
    def smoothed_available_current(self) -> float | None:
        """Return the computed smoothed available current for divert."""
        return self._status.get("smoothed_available_current")

    @property
    def charge_rate(self) -> float | None:
        """Return the divert charge rate."""
        return self._status.get("charge_rate")

    @property
    def divert_active(self) -> bool:
        """Return if divert is active."""
        return bool(self._config.get("divert_enabled", False))

    @property
    def wifi_serial(self) -> str | None:
        """Return wifi serial."""
        return self._config.get("wifi_serial", None)

    @property
    def charging_power(self) -> float | None:
        """Return the charge power.

        Calculate Watts base on V*I
        """
        if self._status is not None and all(
            key in self._status for key in ["voltage", "amp"]
        ):
            return round(self._status["voltage"] * self._status["amp"], 2)
        return None

    # Shaper values
    @property
    def shaper_active(self) -> bool | None:
        """Return if shper is active."""
        return self._status.get("shaper", None)

    @property
    def shaper_live_power(self) -> int | None:
        """Return shaper live power reading."""
        return self._status.get("shaper_live_pwr", None)

    @property
    def shaper_available_current(self) -> float | None:
        """Return shaper available current."""
        shaper_cur = self._status.get("shaper_cur")
        if shaper_cur == 255:
            return self._status.get("pilot")
        return shaper_cur

    @property
    def shaper_max_power(self) -> int | None:
        """Return shaper live power reading."""
        return self._status.get("shaper_max_pwr", None)

    @property
    def shaper_updated(self) -> bool:
        """Return shaper updated boolean."""
        return bool(self._status.get("shaper_updated", False))

    # Vehicle values
    @property
    def vehicle_soc(self) -> int | None:
        """Return battery level."""
        return self._status.get("vehicle_soc", self._status.get("battery_level", None))

    @property
    def vehicle_range(self) -> int | None:
        """Return battery range."""
        return self._status.get(
            "vehicle_range", self._status.get("battery_range", None)
        )

    @property
    def vehicle_eta(self) -> datetime | None:
        """Return time to full charge."""
        value = self._status.get(
            "time_to_full_charge", self._status.get("vehicle_eta", None)
        )
        if value is None:
            return None
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=seconds)

    # There is currently no min/max amps JSON data
    # available via HTTP API methods
    @property
    def min_amps(self) -> int:
        """Return the minimum amps."""
        return self._config.get("min_current_hard", MIN_AMPS)

    @property
    def max_amps(self) -> int:
        """Return the maximum amps."""
        return self._config.get("max_current_hard", MAX_AMPS)

    @property
    def mqtt_connected(self) -> bool:
        """Return the status of the mqtt connection."""
        return bool(self._status.get("mqtt_connected", False))

    @property
    def emoncms_connected(self) -> bool | None:
        """Return the status of the emoncms connection."""
        return self._status.get("emoncms_connected", None)

    @property
    def ocpp_connected(self) -> bool | None:
        """Return the status of the ocpp connection."""
        return self._status.get("ocpp_connected", None)

    @property
    def uptime(self) -> int | None:
        """Return the unit uptime."""
        return self._status.get("uptime", None)

    @property
    def freeram(self) -> int | None:
        """Return the unit freeram."""
        return self._status.get("freeram", None)

    # Safety counts
    @property
    def checks_count(self) -> dict:
        """Return the safety checks counts."""
        attributes = ("gfcicount", "nogndcount", "stuckcount")
        counts = {}
        if self._status is not None and set(attributes).issubset(self._status.keys()):
            counts["gfcicount"] = self._status["gfcicount"]
            counts["nogndcount"] = self._status["nogndcount"]
            counts["stuckcount"] = self._status["stuckcount"]
        return counts

    @property
    async def async_override_state(self) -> str | None:
        """Return the unit override state."""
        try:
            override = await self.get_override()
        except UnsupportedFeature:
            _LOGGER.debug("Override state unavailable on older firmware.")
            return None
        if isinstance(override, dict):
            return override.get("state", "auto")
        return "auto"

    @property
    def current_power(self) -> int:
        """Return the current power (live) in watts."""
        if not self._version_check("4.2.2"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        return self._status.get("power", 0)
