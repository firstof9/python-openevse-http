"""Claims class for OpenEVSE HTTP."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import CLIENT
from .exceptions import UnsupportedFeature

if TYPE_CHECKING:
    from .client import OpenEVSE

_LOGGER = logging.getLogger(__name__)


class Claims:
    """Handle claims for OpenEVSE."""

    def __init__(self, evse: OpenEVSE) -> None:
        """Initialize the claims class."""
        self._evse = evse

    async def make(
        self,
        state: str | None = None,
        charge_current: int | None = None,
        max_current: int | None = None,
        auto_release: bool = True,
        client: int = CLIENT,
    ) -> Any:
        """Make a claim."""
        if not self._evse._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        if state not in ["active", "disabled", None]:
            _LOGGER.error("Invalid claim state: %s", state)
            raise ValueError

        url = f"{self._evse.url}claims/{client}"

        data: dict[str, Any] = {}

        data["auto_release"] = auto_release

        if state is not None:
            data["state"] = state
        if charge_current is not None:
            data["charge_current"] = charge_current
        if max_current is not None:
            data["max_current"] = max_current

        _LOGGER.debug("Claim data: %s", data)
        _LOGGER.debug("Setting up claim on %s", url)
        response = await self._evse.process_request(url=url, method="post", data=data)
        return response

    async def release(self, client: int = CLIENT) -> Any:
        """Delete a claim."""
        if not self._evse._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        url = f"{self._evse.url}claims/{client}"

        _LOGGER.debug("Releasing claim on %s", url)
        response = await self._evse.process_request(url=url, method="delete")
        return response

    async def list(self, target: bool | None = None) -> Any:
        """List all claims."""
        if not self._evse._version_check("4.1.0"):
            _LOGGER.debug("Feature not supported for older firmware.")
            raise UnsupportedFeature

        target_check = ""
        if target:
            target_check = "/target"

        url = f"{self._evse.url}claims{target_check}"

        _LOGGER.debug("Getting claims on %s", url)
        response = await self._evse.process_request(url=url, method="get")
        return response
