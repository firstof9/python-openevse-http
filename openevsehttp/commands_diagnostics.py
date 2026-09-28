"""Diagnostics and hardware commands mixin for OpenEVSE."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .commands_base import BaseCommandMixin
from .const import RAPI_ERRORS, SUCCESS_ANSWERS
from .exceptions import CommandFailedError

_LOGGER = logging.getLogger(__name__)


class DiagnosticsCommandsMixin(BaseCommandMixin):
    """Mixin for OpenEVSE diagnostics and hardware health commands."""

    async def run_stuck_relay_recovery(self) -> None:
        """Run the stuck-relay recovery cycle.

        Requires OpenEVSE controller firmware 9.3.0+.
        On gateway firmware v5.1.0+, uses HTTP POST /relay/recovery.
        On older gateway firmware, falls back to RAPI command $FK.
        Note: The controller will reject ($NK / HTTP 500) if an EV is connected.
        """
        self._require_controller_firmware("9.3.0", "Stuck-relay recovery")

        if self._version_check("5.1.0"):
            _LOGGER.debug("Running stuck-relay recovery via HTTP")
            url = f"{self.url}relay/recovery"
            response = await self.process_request(url=url, method="post")
            response = self._normalize_response(response)
            msg = response.get("msg") if isinstance(response, Mapping) else None
            if msg not in SUCCESS_ANSWERS:
                _LOGGER.error("Problem running stuck-relay recovery: %s", response)
                raise CommandFailedError(
                    f"Problem running stuck-relay recovery: {response}"
                )
        else:
            _LOGGER.debug("Running stuck-relay recovery via RAPI")
            command = "$FK"
            reply, response = await self.send_command(command)
            if reply in [False, "NK"] or (
                isinstance(response, str)
                and (response.startswith("$NK") or response in RAPI_ERRORS)
            ):
                _LOGGER.error(
                    "Problem running stuck-relay recovery via RAPI: %s", response
                )
                raise CommandFailedError(
                    f"Problem running stuck-relay recovery via RAPI: {response}"
                )

    async def reset_relay_health(self) -> None:
        """Reset the relay contact-life health estimation metrics.

        Use after a physical relay replacement so wear metrics do not carry over.
        Requires OpenEVSE controller firmware 9.3.0+.
        On gateway firmware v5.1.0+, uses HTTP POST /relay/reset.
        On older gateway firmware, falls back to RAPI command $FH.
        """
        self._require_controller_firmware("9.3.0", "Resetting relay health")

        if self._version_check("5.1.0"):
            _LOGGER.debug("Resetting relay health via HTTP")
            url = f"{self.url}relay/reset"
            response = await self.process_request(url=url, method="post")
            response = self._normalize_response(response)
            msg = response.get("msg") if isinstance(response, Mapping) else None
            if msg not in SUCCESS_ANSWERS:
                _LOGGER.error("Problem resetting relay health: %s", response)
                raise CommandFailedError(f"Problem resetting relay health: {response}")
        else:
            _LOGGER.debug("Resetting relay health via RAPI")
            command = "$FH"
            reply, response = await self.send_command(command)
            if reply in [False, "NK"] or (
                isinstance(response, str)
                and (response.startswith("$NK") or response in RAPI_ERRORS)
            ):
                _LOGGER.error("Problem resetting relay health via RAPI: %s", response)
                raise CommandFailedError(
                    f"Problem resetting relay health via RAPI: {response}"
                )

    async def get_cable_temp(self) -> dict[str, Any]:
        """Get cable temperature monitoring status, sources, and calibration.

        Requires OpenEVSE controller firmware 9.4.0+ and gateway firmware 5.1.0+.
        """
        self._require_controller_firmware("9.4.0", "Cable temperature monitoring")
        self._require_firmware("5.1.0", "Cable temperature endpoint")

        url = f"{self.url}cabletemp"
        response = await self.process_request(url=url, method="get")
        if not isinstance(response, dict):
            _LOGGER.error("Invalid response from /cabletemp: %s", response)
            raise CommandFailedError(f"Invalid response from /cabletemp: {response}")
        return response

    async def set_cable_temp(
        self,
        source: int,
        pin: int,
        r25: int | None = None,
        beta: int | None = None,
        offset_c10: int | None = None,
        panic_c10: int | None = None,
    ) -> None:
        """Configure cable temperature sensor source and calibration.

        :param source: Logical source index (0=ev1, 1=ev2, 2=in1, 3=in2).
        :param pin: Pin assignment (0=unassigned, 1=PP_READ, 2=PP2_READ).
        :param r25: Thermistor resistance at 25C (Ohms).
        :param beta: Thermistor beta coefficient.
        :param offset_c10: Calibration offset in tenths of a degree C.
        :param panic_c10: Shutdown threshold in tenths of a degree C.
        """
        self._require_controller_firmware("9.4.0", "Cable temperature monitoring")
        self._require_firmware("5.1.0", "Cable temperature endpoint")

        if (
            not isinstance(source, int)
            or isinstance(source, bool)
            or not (0 <= source <= 3)
        ):
            raise ValueError("source must be an integer between 0 and 3.")
        if not isinstance(pin, int) or isinstance(pin, bool) or not (0 <= pin <= 2):
            raise ValueError("pin must be an integer between 0 and 2.")

        data: dict[str, Any] = {"source": source, "pin": pin}
        cal_fields = [r25, beta, offset_c10, panic_c10]
        has_cal = all(f is not None for f in cal_fields)
        any_cal = any(f is not None for f in cal_fields)

        if any_cal and not has_cal:
            raise ValueError(
                "r25, beta, offset_c10, and panic_c10 must all be provided together."
            )

        if has_cal:
            for name, val in [
                ("r25", r25),
                ("beta", beta),
                ("offset_c10", offset_c10),
                ("panic_c10", panic_c10),
            ]:
                if not isinstance(val, int) or isinstance(val, bool):
                    raise TypeError(f"{name} must be an integer.")
            data.update(
                {
                    "r25": r25,
                    "beta": beta,
                    "offset_c10": offset_c10,
                    "panic_c10": panic_c10,
                }
            )

        url = f"{self.url}cabletemp"
        _LOGGER.debug("Setting cable temperature config: %s", data)
        response = await self.process_request(url=url, method="post", data=data)
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem configuring cable temperature: %s", response)
            raise CommandFailedError(
                f"Problem configuring cable temperature: {response}"
            )

    async def set_cable_temp_enabled(self, enable: bool = True) -> None:
        """Enable or disable cable temperature monitoring."""
        self._require_controller_firmware("9.4.0", "Cable temperature monitoring")

        if not isinstance(enable, bool):
            raise TypeError("Value must be a boolean.")

        url = f"{self.url}config"
        data = {"cable_temp": enable}

        _LOGGER.debug("Setting cable_temp to %s", enable)
        response = await self.process_request(url=url, method="post", data=data)
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem toggling cable_temp: %s", response)
            raise CommandFailedError(f"Problem toggling cable_temp: {response}")

        self._config["cable_temp"] = enable

    async def get_logs(
        self, index: int | None = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Retrieve log event block information or specific log event block.

        When index is None, queries 'GET /logs' and returns a dict with 'min' and 'max'
        block index bounds (e.g. {'min': 0, 'max': 12}).
        When index is an integer, queries 'GET /logs/{index}' and returns a list of log event dicts.

        Requires gateway firmware 4.0.0 or higher.

        :param index: Block index integer, or None for block range info.
        :return: Dict containing 'min' and 'max' block indices, or list of event dicts.
        """
        self._require_firmware("4.0.0", "get_logs")

        if index is not None:
            if not isinstance(index, int) or isinstance(index, bool):
                raise TypeError("index must be an integer.")
            url = f"{self.url}logs/{index}"
        else:
            url = f"{self.url}logs"

        _LOGGER.debug("Querying logs: %s", url)
        response = await self.process_request(url=url, method="get")

        if index is not None:
            if not isinstance(response, list):
                _LOGGER.error("Invalid response from /logs/%s: %s", index, response)
                raise CommandFailedError(
                    f"Invalid response from /logs/{index}: {response}"
                )
            return [dict(item) for item in response if isinstance(item, Mapping)]

        if not isinstance(response, Mapping):
            _LOGGER.error("Invalid response from /logs: %s", response)
            raise CommandFailedError(f"Invalid response from /logs: {response}")

        return dict(response)
