"""Core command methods for the OpenEVSE charger."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .commands_base import BaseCommandMixin
from .const import MAX_AMPS, MIN_AMPS, RAPI_ERRORS, SUCCESS_ANSWERS, divert_mode
from .exceptions import (
    CommandFailedError,
    UnknownStateError,
    UnsupportedFeature,
)

_LOGGER = logging.getLogger(__name__)


class CoreCommandsMixin(BaseCommandMixin):
    """Mixin providing core charger operation commands."""

    async def set_charge_mode(self, mode: str = "fast") -> None:
        """Set the charge mode at startup setting."""
        url = f"{self.url}config"

        if mode not in ["fast", "eco"]:
            _LOGGER.error("Invalid value for charge_mode: %s", mode)
            raise ValueError(f"charge_mode must be 'fast' or 'eco', got {mode!r}")

        data = {"charge_mode": mode}

        _LOGGER.debug("Setting charge mode to %s", mode)
        response = await self.process_request(url=url, method="post", data=data)
        response = self._normalize_response(response)
        msg = response.get("msg") if isinstance(response, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem issuing command: %s", response)
            raise CommandFailedError(f"Problem issuing command: {response}")

    async def divert_mode(self) -> Mapping[str, Any] | list[Any]:
        """Set the divert mode to either Normal or Eco modes."""
        if not self._config:
            raise UnknownStateError("Missing configuration: self._config is required")

        self._require_firmware("2.9.1", "divert_mode")

        if "divert_enabled" in self._config:
            _LOGGER.debug("Divert Enabled: %s", self._config["divert_enabled"])
            mode = not self._config["divert_enabled"]
        else:
            _LOGGER.debug("Unable to check divert status.")
            raise UnsupportedFeature

        url = f"{self.url}config"
        data = {"divert_enabled": mode}

        _LOGGER.debug("Toggling divert: %s", mode)
        response = await self.process_request(url=url, method="post", data=data)
        _LOGGER.debug("divert_mode response: %s", response)
        normalized_response = self._normalize_response(response)
        if (
            isinstance(normalized_response, dict)
            and normalized_response.get("msg") in SUCCESS_ANSWERS
        ):
            self._config["divert_enabled"] = mode
        return normalized_response

    async def get_override(self) -> Mapping[str, Any] | list[Any]:
        """Get the manual override status."""
        self._require_firmware("4.0.1", "get_override")
        url = f"{self.url}override"

        _LOGGER.debug("Getting data from %s", url)
        response = await self.process_request(url=url, method="get")
        return self._normalize_response(response)

    async def set_override(
        self,
        state: str | None = None,
        charge_current: int | None = None,
        max_current: int | None = None,
        energy_limit: int | None = None,
        time_limit: int | None = None,
        auto_release: bool | None = None,
    ) -> Any:
        """Set the manual override status.

        Fetches the current override payload first and merges existing values
        into the request payload. This prevents the firmware from clearing/resetting
        previously configured properties that are not passed in the function call.
        """
        self._require_firmware("4.0.1", "set_override")
        url = f"{self.url}override"

        response = await self.get_override()
        if not isinstance(response, Mapping) or (
            len(response) == 1 and "msg" in response
        ):
            _LOGGER.error("Invalid override payload: %s", response)
            raise ValueError("Invalid override state response")

        if state not in ["active", "disabled", None]:
            _LOGGER.error("Invalid override state: %s", state)
            raise ValueError

        data: dict[str, Any] = {}
        if isinstance(response, Mapping):
            for key in (
                "state",
                "charge_current",
                "max_current",
                "energy_limit",
                "time_limit",
                "auto_release",
            ):
                if key in response:
                    data[key] = response[key]

        if auto_release is not None:
            data["auto_release"] = auto_release

        if state is not None:
            data["state"] = state
        if charge_current is not None:
            data["charge_current"] = charge_current
        if max_current is not None:
            data["max_current"] = max_current
        if energy_limit is not None:
            data["energy_limit"] = energy_limit
        if time_limit is not None:
            data["time_limit"] = time_limit

        _LOGGER.debug("Override data: %s", data)
        _LOGGER.debug("Setting override config on %s", url)
        reply = await self.process_request(url=url, method="post", data=data)
        return self._normalize_response(reply)

    async def toggle_override(self) -> None:
        """Toggle the manual override status."""
        #   3.x: use RAPI commands $FE (enable) and $FS (sleep)
        #   4.x: use HTTP API call
        lower = "4.0.1"
        if self._version_check(lower):
            url = f"{self.url}override"

            _LOGGER.debug("Toggling manual override %s", url)
            response = await self.process_request(url=url, method="patch")
            response = self._normalize_response(response)
            _LOGGER.debug("Toggle response: %s", response)
            if (
                not isinstance(response, Mapping)
                or response.get("msg") not in SUCCESS_ANSWERS
            ):
                _LOGGER.error("Problem toggling override: %s", response)
                raise CommandFailedError(f"Failed to toggle override: {response}")
        else:
            # Older firmware use RAPI commands
            _LOGGER.debug("Toggling manual override via RAPI")
            if "state" not in self._status:
                await self.update()

            if "state" not in self._status:
                _LOGGER.error("Cannot toggle override: unknown charger state.")
                raise UnknownStateError(
                    "Cannot toggle override: unknown charger state."
                )

            command = "$FE" if self._status.get("state") == 254 else "$FS"
            response, msg = await self.send_command(command)
            _LOGGER.debug("Toggle response: %s", msg)
            if response in [False, "NK"] or (
                isinstance(msg, str) and (msg.startswith("$NK") or msg in RAPI_ERRORS)
            ):
                _LOGGER.error("Problem toggling override via RAPI: %s", msg)
                raise CommandFailedError(f"Failed to toggle override via RAPI: {msg}")

    async def clear_override(self) -> None:
        """Clear the manual override status."""
        self._require_firmware("4.0.1", "clear_override")
        url = f"{self.url}override"

        _LOGGER.debug("Clearing manual override %s", url)
        response = await self.process_request(url=url, method="delete")
        response = self._normalize_response(response)
        msg = response.get("msg") if isinstance(response, Mapping) else None
        _LOGGER.debug("Clear override response: %s", msg)
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem clearing override: %s", response)
            raise CommandFailedError(f"Failed to clear override: {response}")

    async def enable_override(self) -> None:
        """Enable manual override idempotently.

        On firmware >= 4.0.1, sets override state to active.
        On older firmware (< 4.0.1), sends $FE only if sleeping (state 254).
        """
        lower = "4.0.1"
        if self._version_check(lower):
            _LOGGER.debug("Enabling manual override via HTTP API")
            await self.set_override(state="active")
        else:
            _LOGGER.debug("Enabling manual override via RAPI")
            await self.update(force_status=True)

            if "state" not in self._status:
                _LOGGER.error("Cannot enable override: unknown charger state.")
                raise UnknownStateError(
                    "Cannot enable override: unknown charger state."
                )

            if self._status.get("state") == 254:
                response, msg = await self.send_command("$FE")
                _LOGGER.debug("Enable override response: %s", msg)
                if response in [False, "NK"] or (
                    isinstance(msg, str)
                    and (msg.startswith("$NK") or msg in RAPI_ERRORS)
                ):
                    _LOGGER.error("Problem enabling override via RAPI: %s", msg)
                    raise CommandFailedError(
                        f"Failed to enable override via RAPI: {msg}"
                    )
                # Successful $FE wakes the charger from sleep (state 254)
                self._status["state"] = 2
            else:
                _LOGGER.debug(
                    "Manual override already active (state %s), skipping $FE",
                    self._status.get("state"),
                )

    async def disable_override(self) -> None:
        """Disable/clear manual override idempotently.

        On firmware >= 4.0.1, clears the override record via DELETE /override.
        On older firmware (< 4.0.1), sends $FS only if not sleeping (state != 254).
        """
        lower = "4.0.1"
        if self._version_check(lower):
            _LOGGER.debug("Disabling manual override via HTTP API")
            await self.clear_override()
        else:
            _LOGGER.debug("Disabling manual override via RAPI")
            await self.update(force_status=True)

            if "state" not in self._status:
                _LOGGER.error("Cannot disable override: unknown charger state.")
                raise UnknownStateError(
                    "Cannot disable override: unknown charger state."
                )

            if self._status.get("state") != 254:
                response, msg = await self.send_command("$FS")
                _LOGGER.debug("Disable override response: %s", msg)
                if response in [False, "NK"] or (
                    isinstance(msg, str)
                    and (msg.startswith("$NK") or msg in RAPI_ERRORS)
                ):
                    _LOGGER.error("Problem disabling override via RAPI: %s", msg)
                    raise CommandFailedError(
                        f"Failed to disable override via RAPI: {msg}"
                    )
                # Successful $FS puts the charger into sleep (state 254)
                self._status["state"] = 254
            else:
                _LOGGER.debug(
                    "Manual override already disabled (state 254), skipping $FS"
                )

    async def set_manual_override(self, enable: bool) -> None:
        """Set the manual override state idempotently."""
        if enable:
            await self.enable_override()
        else:
            await self.disable_override()

    async def set_current(self, amps: int = 6) -> None:
        """Set the soft current limit."""
        #   3.x - 4.1.0: use RAPI commands $SC <amps>
        #   4.1.2: use HTTP API call
        if isinstance(amps, bool) or not isinstance(amps, int):
            _LOGGER.error("Invalid type for current limit: %s (%s)", amps, type(amps))
            raise ValueError(
                f"Current limit must be an integer, got {type(amps).__name__}"
            )

        min_current = self._config.get("min_current_hard", MIN_AMPS)
        max_current = self._config.get("max_current_hard", MAX_AMPS)
        if amps < min_current or amps > max_current:
            _LOGGER.error("Invalid value for current limit: %s", amps)
            raise ValueError(
                f"Current limit {amps} is out of range ({min_current}-{max_current})"
            )

        if self._version_check("4.1.2"):
            _LOGGER.debug("Setting current limit to %s", amps)
            response = await self.set_override(charge_current=amps)
            _LOGGER.debug("Set current response: %s", response)
            if (
                not isinstance(response, Mapping)
                or response.get("msg") not in SUCCESS_ANSWERS
            ):
                _LOGGER.error("Problem setting current limit: %s", response)
                raise CommandFailedError(f"Problem setting current limit: {response}")

        else:
            # RAPI commands
            _LOGGER.debug("Setting current via RAPI")
            command = f"$SC {amps} N"
            # Different parameters for older firmware
            if self._version_check("2.9.1"):
                command = f"$SC {amps} V"
            response, msg = await self.send_command(command)
            _LOGGER.debug("Set current response: %s", msg)
            if response in [False, "NK"] or (
                isinstance(msg, str) and (msg.startswith("$NK") or msg in RAPI_ERRORS)
            ):
                _LOGGER.error("Problem setting current via RAPI: %s", msg)
                raise CommandFailedError(f"Problem setting current via RAPI: {msg}")

    async def set_service_level(self, level: int | str = 2) -> None:
        """Set the service level of the EVSE."""
        if isinstance(level, bool) or (
            not (isinstance(level, int) and 0 <= level <= 2) and level != "A"
        ):
            _LOGGER.error("Invalid service level: %s", level)
            raise ValueError

        url = f"{self.url}config"
        data = {"service": level}

        _LOGGER.debug("Set service level to: %s", level)
        response = await self.process_request(url=url, method="post", data=data)
        response = self._normalize_response(response)
        _LOGGER.debug("service response: %s", response)
        msg = response.get("msg") if isinstance(response, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem issuing command: %s", response)
            raise CommandFailedError(f"Problem issuing command: {response}")

    # Restart OpenEVSE WiFi
    async def restart_wifi(self) -> None:
        """Restart OpenEVSE WiFi module."""
        url = f"{self.url}restart"
        data = {"device": "gateway"}

        response = await self.process_request(url=url, method="post", data=data)
        response = self._normalize_response(response)

        msg = (
            response.get("msg", "Unknown error")
            if isinstance(response, Mapping)
            else "Unknown error"
        )
        _LOGGER.debug("WiFi Restart response: %s", msg)

        # Strict success check:
        # 1. Must be a Mapping
        # 2. Must NOT have an "error" key
        # 3. Must have "result" in ("OK", "ok", True) OR "success" is True
        #    OR "msg" indicating restart acknowledgment ("restart gateway", "ok")
        success = (
            isinstance(response, Mapping)
            and not response.get("error")
            and (
                response.get("result") in ("OK", "ok", True)
                or response.get("success") is True
                or (
                    isinstance(response.get("msg"), str)
                    and any(
                        val in response["msg"].lower()
                        for val in ("ok", "restart gateway")
                    )
                )
            )
        )
        if success and isinstance(response, Mapping) and "msg" in response:
            msg_val = str(response["msg"]).lower()
            if (
                msg_val != "ok"
                and "ok" not in msg_val
                and "restart gateway" not in msg_val
            ):
                success = False

        if not success:
            _LOGGER.error("Problem restarting WiFi: %s", response)
            raise CommandFailedError(f"Failed to restart WiFi: {msg}")

    # Restart EVSE module
    async def restart_evse(self) -> None:
        """Restart EVSE module."""
        if self._version_check("5.0.0"):
            _LOGGER.debug("Restarting EVSE module via HTTP")
            url = f"{self.url}restart"
            data = {"device": "evse"}
            reply = await self.process_request(url=url, method="post", data=data)
            reply = self._normalize_response(reply)
            if not isinstance(reply, Mapping) or (
                reply.get("result") not in (None, 0, "OK", "ok", True)
                or reply.get("msg") in RAPI_ERRORS
                or reply.get("msg") in ["NK", False]
                or reply.get("error")
            ):
                _LOGGER.error("Problem restarting EVSE module via HTTP: %s", reply)
                raise CommandFailedError(
                    f"Failed to restart EVSE module via HTTP: {reply}"
                )

            response = (
                reply.get("msg", "Unknown error")
                if isinstance(reply, Mapping)
                else "Unknown error"
            )

        else:
            _LOGGER.debug("Restarting EVSE module via RAPI")
            command = "$FR"
            reply, response = await self.send_command(command)
            if reply in [False, "NK"] or (
                isinstance(response, str)
                and (response.startswith("$NK") or response in RAPI_ERRORS)
            ):
                _LOGGER.error("Problem restarting EVSE module via RAPI: %s", response)
                raise CommandFailedError(
                    f"Failed to restart EVSE module via RAPI: {response}"
                )

        _LOGGER.debug("EVSE Restart response: %s", response)

    async def set_led_brightness(self, level: int) -> None:
        """Set LED brightness level."""
        if isinstance(level, bool) or not isinstance(level, int):
            _LOGGER.error(
                "Invalid type for LED brightness: %s (%s)", level, type(level)
            )
            raise TypeError(
                f"LED brightness must be an integer, got {type(level).__name__}"
            )
        if not 0 <= level <= 255:
            _LOGGER.error("Invalid value for LED brightness: %s", level)
            raise ValueError(f"LED brightness {level} is out of range (0-255)")

        self._require_firmware("4.1.0", "set_led_brightness")

        url = f"{self.url}config"
        data: dict[str, Any] = {}

        data["led_brightness"] = level
        _LOGGER.debug("Setting LED brightness to %s", level)
        response = await self.process_request(url=url, method="post", data=data)
        response = self._normalize_response(response)
        msg = response.get("msg") if isinstance(response, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem issuing command: %s", response)
            raise CommandFailedError(f"Problem issuing command: {response}")

    async def set_divert_mode(self, mode: str = "fast") -> None:
        """Set the divert mode.

        Note: The OpenEVSE WiFi `/divertmode` endpoint expects form-encoded
        data (`divertmode={mode_int}`) rather than a JSON payload, passed via
        the client's `rapi` data parameter.
        """
        url = f"{self.url}divertmode"
        if mode not in ["fast", "eco"]:
            _LOGGER.error("Invalid value for divert mode: %s", mode)
            raise ValueError(f"divert mode must be 'fast' or 'eco', got {mode!r}")
        _LOGGER.debug("Setting divert mode to %s", mode)
        # convert text to int
        new_mode = divert_mode[mode]

        data = f"divertmode={new_mode}"

        response = await self.process_request(url=url, method="post", rapi=data)
        success = False
        if isinstance(response, str):
            res_lower = response.lower()
            if "divert" in res_lower and "changed" in res_lower:
                success = True
        elif isinstance(response, dict) and response.get("msg") in SUCCESS_ANSWERS:
            success = True

        if not success:
            _LOGGER.error("Problem issuing command: %s", response)
            raise CommandFailedError(f"Problem issuing command: {response}")

        self._status["divertmode"] = new_mode

    async def set_shaper(self, enable: bool = True) -> None:
        """Set shaper mode."""
        self._require_firmware("4.0.0", "set_shaper")

        url = f"{self.url}shaper"
        mode = 1 if enable else 0
        data = {"shaper": mode}

        _LOGGER.debug("Setting shaper to %s", mode)
        response = await self.process_request(url=url, method="post", rapi=data)
        response = self._normalize_response(response)
        msg = response.get("msg") if isinstance(response, Mapping) else None
        if msg not in SUCCESS_ANSWERS and msg != "Current Shaper state changed":
            _LOGGER.error("Problem issuing command: %s", response)
            raise CommandFailedError(f"Problem issuing command: {response}")

        self._status["shaper"] = mode

    async def toggle_shaper(self) -> None:
        """Toggle shaper mode."""
        shaper_active = self._status.get("shaper")
        if shaper_active is None:
            await self.update()
            shaper_active = self._status.get("shaper")

        if shaper_active is None:
            _LOGGER.error("Cannot toggle shaper: unknown shaper state.")
            raise UnknownStateError("Cannot toggle shaper: unknown shaper state.")

        new_state = not bool(shaper_active)
        await self.set_shaper(new_state)

    async def set_mqtt_vehicle_range_miles(self, enable: bool = True) -> None:
        """Set mqtt_vehicle_range_miles configuration setting.

        Dynamically changing this setting will affect future evaluations of
        the vehicle_range_with_unit property.
        """
        if not isinstance(enable, bool):
            raise TypeError("Value must be a boolean.")

        url = f"{self.url}config"
        data = {"mqtt_vehicle_range_miles": enable}

        _LOGGER.debug("Setting mqtt_vehicle_range_miles to %s", enable)
        response = await self.process_request(url=url, method="post", data=data)
        response = self._normalize_response(response)
        msg = response.get("msg") if isinstance(response, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem issuing command: %s", response)
            raise CommandFailedError(f"Problem issuing command: {response}")
