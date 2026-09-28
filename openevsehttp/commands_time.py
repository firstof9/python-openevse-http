"""Time and RTC commands mixin for OpenEVSE."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .commands_base import BaseCommandMixin
from .const import RAPI_ERRORS, SUCCESS_ANSWERS
from .exceptions import CommandFailedError

_LOGGER = logging.getLogger(__name__)


class TimeCommandsMixin(BaseCommandMixin):
    """Mixin for OpenEVSE time and RTC commands."""

    async def get_time(self) -> dict[str, Any]:
        """Get time and NTP synchronization status from charger.

        On WiFi firmware v4.0.0+, queries GET /time.
        On older firmware (v2.x/v3.x), returns synthesized dict from status/config.
        """
        if self._version_check("4.0.0"):
            url = f"{self.url}time"
            response = await self.process_request(url=url, method="get")
            if not isinstance(response, dict):
                _LOGGER.error("Invalid response from /time: %s", response)
                raise CommandFailedError(f"Invalid response from /time: {response}")
            return response

        # Older firmware fallback from _status and _config
        return {
            "time": self._status.get("time"),
            "offset": self._status.get("offset"),
            "local_time": None,
        }

    @staticmethod
    def _format_time_str(target_time: datetime | str | None) -> str | None:
        """Format target time into ISO-8601 UTC string."""
        if target_time is None:
            return None
        if isinstance(target_time, datetime):
            utc_dt = (
                target_time.astimezone(timezone.utc)
                if target_time.tzinfo is not None
                else target_time
            )
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(target_time, str):
            return target_time
        raise TypeError("target_time must be a datetime or ISO-8601 string.")

    async def _set_time_v4(
        self,
        time_str: str | None,
        timezone_str: str | None,
        sntp: bool | None,
    ) -> None:
        """Set time via v4 HTTP API."""
        if sntp is not None and not isinstance(sntp, bool):
            raise TypeError("sntp must be a boolean.")
        if timezone_str is not None and not isinstance(timezone_str, str):
            raise TypeError("timezone_str must be a string.")

        sntp_val = (
            sntp if sntp is not None else bool(self._config.get("sntp_enabled", True))
        )
        tz_val = timezone_str or self._config.get("time_zone", "UTC0")
        data: dict[str, Any] = {
            "sntp_enabled": sntp_val,
            "time_zone": tz_val,
        }
        if time_str is not None:
            data["time"] = time_str
        elif not sntp_val:
            data["time"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{self.url}time"
        _LOGGER.debug("Setting time via HTTP: %s", data)
        response = await self.process_request(url=url, method="post", data=data)
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS and msg != "set":
            _LOGGER.error("Problem setting time: %s", response)
            raise CommandFailedError(f"Problem setting time: {response}")

        self._config["sntp_enabled"] = sntp_val
        self._config["time_zone"] = tz_val

    async def _set_time_v3(
        self,
        time_str: str | None,
        timezone_str: str | None,
        sntp: bool | None,
    ) -> None:
        """Set time via legacy v3 /settime HTTP API."""
        data: dict[str, Any] = {}
        if sntp is not None:
            data["sntp_enabled"] = sntp
        if timezone_str is not None:
            data["time_zone"] = timezone_str
        if time_str is not None:
            data["time"] = time_str
        elif sntp is False:
            data["time"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{self.url}settime"
        _LOGGER.debug("Setting time via legacy /settime: %s", data)
        response = await self.process_request(url=url, method="post", data=data)
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS and msg != "set":
            _LOGGER.error("Problem setting time via /settime: %s", response)
            raise CommandFailedError(f"Problem setting time: {response}")

    async def _set_time_v2(self, target_time: datetime | str | None) -> None:
        """Set time via legacy RAPI $S1 command."""
        if target_time is not None:
            if isinstance(target_time, datetime):
                dt = target_time
            elif isinstance(target_time, str):
                try:
                    clean_str = target_time.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(clean_str)
                except ValueError as err:
                    raise ValueError(
                        f"Could not parse date string: {target_time}"
                    ) from err
            else:
                raise TypeError("target_time must be a datetime or ISO-8601 string.")
        else:
            dt = datetime.now(timezone.utc)

        yr = dt.year % 100
        cmd = f"$S1 {yr:02d} {dt.month:02d} {dt.day:02d} {dt.hour:02d} {dt.minute:02d} {dt.second:02d}"
        _LOGGER.debug("Setting RTC time via RAPI: %s", cmd)
        reply, response = await self.send_command(cmd)
        if reply in [False, "NK"] or (
            isinstance(response, str)
            and (response.startswith("$NK") or response in RAPI_ERRORS)
        ):
            _LOGGER.error("Problem setting RTC via RAPI: %s", response)
            raise CommandFailedError(f"Problem setting RTC via RAPI: {response}")

    async def set_time(
        self,
        target_time: datetime | str | None = None,
        timezone_str: str | None = None,
        sntp: bool | None = None,
    ) -> None:
        """Set charger date, time, and timezone.

        :param target_time: datetime object or ISO-8601 string (e.g. '2026-03-25T15:30:00Z').
                            If None and sntp is False, defaults to current UTC time.
        :param timezone_str: POSIX timezone string or location (e.g. 'America/New_York|EST5EDT...').
        :param sntp: Boolean flag to enable or disable SNTP/NTP synchronization.
        """
        if self._version_check("4.0.0"):
            time_str = self._format_time_str(target_time)
            await self._set_time_v4(time_str, timezone_str, sntp)
        elif self._version_check("3.0.0"):
            time_str = self._format_time_str(target_time)
            await self._set_time_v3(time_str, timezone_str, sntp)
        else:
            await self._set_time_v2(target_time)

    async def sync_time(self) -> None:
        """Trigger an immediate NTP time synchronization on the charger.

        Sends POST /time with '{"sync_now": true}' on firmware v4.0.0+.
        """
        self._require_firmware("4.0.0", "sync_time")

        url = f"{self.url}time"
        data = {"sync_now": True}
        _LOGGER.debug("Triggering NTP sync: %s", data)
        response = await self.process_request(url=url, method="post", data=data)
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS and msg != "set":
            _LOGGER.error("Problem triggering NTP sync: %s", response)
            raise CommandFailedError(f"Problem triggering NTP sync: {response}")
