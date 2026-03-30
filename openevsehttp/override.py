"""Manual override class for OpenEVSE HTTP."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .exceptions import UnknownError, UnsupportedFeature

if TYPE_CHECKING:
    from .client import OpenEVSE

_LOGGER = logging.getLogger(__name__)


class Override:
    """Handle manual overrides for OpenEVSE."""

    def __init__(self, evse: OpenEVSE) -> None:
        """Initialize the override class."""
        self._evse = evse

    async def get(self) -> dict[str, str] | dict[str, Any]:
        """Get the manual override status."""
        if not self._evse._version_check("4.0.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        url = f"{self._evse.url}override"

        _LOGGER.debug("Getting data from %s", url)
        response = await self._evse.process_request(url=url, method="get")
        return response

    async def set(
        self,
        state: str | None = None,
        charge_current: int | None = None,
        max_current: int | None = None,
        energy_limit: int | None = None,
        time_limit: int | None = None,
        auto_release: bool | None = None,
    ) -> Any:
        """Set the manual override status."""
        if not self._evse._version_check("4.0.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        url = f"{self._evse.url}override"

        data: dict[str, Any] = await self.get()
        if not isinstance(data, dict) or data.get("ok") is False or "state" not in data:
            _LOGGER.error("Failed to retrieve current override state: %s", data)
            raise UnknownError

        if state not in ["active", "disabled", None]:
            _LOGGER.error("Invalid override state: %s", state)
            raise ValueError

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
        response = await self._evse.process_request(url=url, method="post", data=data)
        if not response.get("ok", True) or response.get("msg") in (
            "failed",
            "error",
        ):
            _LOGGER.error("Problem setting override. Response: %s", response)
            raise UnknownError
        return response

    async def toggle(self) -> None:
        """Toggle the manual override status."""
        #   3.x: use RAPI commands $FE (enable) and $FS (sleep)
        #   4.x: use HTTP API call
        lower = "4.0.1"
        if self._evse._version_check(lower):
            url = f"{self._evse.url}override"

            _LOGGER.debug("Toggling manual override %s", url)
            response = await self._evse.process_request(url=url, method="patch")
            if not response.get("ok", True) or response.get("msg") in (
                "failed",
                "error",
            ):
                _LOGGER.error("Problem toggling override. Response: %s", response)
                raise UnknownError
            _LOGGER.debug("Toggle response: %s", response)
        else:
            # Older firmware use RAPI commands
            if (
                not self._evse._status
                or "state" not in self._evse._status
                or self._evse._status["state"] is None
            ):
                await self._evse.update()

            try:
                int_state = int(self._evse._status["state"])
            except (ValueError, TypeError, KeyError):
                _LOGGER.error("Cannot toggle override: current state is unknown")
                raise UnknownError from None

            if int_state == 0:
                _LOGGER.error("Cannot toggle override: current state is unknown")
                raise UnknownError

            _LOGGER.debug(
                "Toggling manual override via RAPI. Current state: %s", int_state
            )
            command = "$FE" if int_state == 254 else "$FS"
            rapi_response = await self._evse.send_command(command)
            if isinstance(rapi_response, dict):
                _LOGGER.error(
                    "Problem toggling override (%s): %s", command, rapi_response
                )
                raise UnknownError

            cmd_sent, resp = rapi_response
            if not resp.startswith("$OK"):
                _LOGGER.error(
                    "Problem issuing command %s. Response: %s", cmd_sent, resp
                )
                raise UnknownError
            _LOGGER.debug("Toggle response: %s", resp)

    async def clear(self) -> None:
        """Clear the manual override status."""
        if not self._evse._version_check("4.0.1"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature
        url = f"{self._evse.url}override"

        _LOGGER.debug("Clearing manual override %s", url)
        response = await self._evse.process_request(url=url, method="delete")
        if not response.get("ok", True) or response.get("msg") in (
            "failed",
            "error",
        ):
            _LOGGER.error("Problem clearing override. Response: %s", response)
            raise UnknownError

        msg = response.get("msg") if isinstance(response, dict) else response
        _LOGGER.debug("Clear response: %s", msg)
