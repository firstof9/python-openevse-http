"""Schedule management command methods for the OpenEVSE charger."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .commands_base import BaseCommandMixin
from .const import SUCCESS_ANSWERS
from .exceptions import CommandFailedError

_LOGGER = logging.getLogger(__name__)


class ScheduleCommandsMixin(BaseCommandMixin):
    """Mixin providing schedule management commands."""

    async def get_schedule(
        self, event_id: int | None = None
    ) -> Mapping[str, Any] | list[Any]:
        """Return the current schedule or a specific schedule event.

        Sends 'GET /schedule' (or 'GET /schedule/{event_id}').
        Falls back to POST if GET is rejected with 405 Method Not Allowed
        on older firmware.

        Requires gateway firmware 4.0.0 or higher.

        :param event_id: Optional schedule event ID integer.
        :return: List of schedule event dicts or dict for a single event.
        """
        self._require_firmware("4.0.0", "get_schedule")

        if event_id is not None:
            if not isinstance(event_id, int) or isinstance(event_id, bool):
                raise TypeError("event_id must be an integer.")
            url = f"{self.url}schedule/{event_id}"
        else:
            url = f"{self.url}schedule"

        _LOGGER.debug("Getting schedule from %s", url)
        response = await self.process_request(url=url, method="get")

        # If GET returned 405 Method Not Allowed (older firmware), fall back to POST
        if (
            isinstance(response, Mapping)
            and response.get("msg") == "Method not allowed"
        ):
            _LOGGER.debug("GET %s returned 405, attempting POST fallback", url)
            response = await self.process_request(url=url, method="post")

        if isinstance(response, Mapping) and response.get("msg") == "Not found":
            _LOGGER.error("Schedule event %s not found: %s", event_id, response)
            raise CommandFailedError(f"Schedule event not found: {response}")

        if not isinstance(response, Mapping | list):
            _LOGGER.error("Invalid response format for /schedule: %s", response)
            raise CommandFailedError(
                f"Invalid response format for /schedule: {response}"
            )

        return self._normalize_response(response)

    async def set_schedule(
        self,
        event: Mapping[str, Any] | list[Mapping[str, Any]],
        event_id: int | None = None,
    ) -> None:
        """Create or update schedule events.

        Sends 'POST /schedule' (or 'POST /schedule/{event_id}').
        Accepts a dictionary representing a single event, a list of event
        dictionaries, or an individual event dictionary with an explicit event_id.

        Requires gateway firmware 4.0.0 or higher.

        :param event: Event dict or list of event dicts to create or update.
        :param event_id: Optional event ID integer when updating a specific event.
        """
        self._require_firmware("4.0.0", "set_schedule")

        if event_id is not None:
            if not isinstance(event_id, int) or isinstance(event_id, bool):
                raise TypeError("event_id must be an integer.")
            if not isinstance(event, Mapping):
                raise TypeError("event must be a mapping when event_id is specified.")
            url = f"{self.url}schedule/{event_id}"
        else:
            if not isinstance(event, Mapping) and not isinstance(event, list):
                raise TypeError("event must be a mapping or a list of mappings.")
            url = f"{self.url}schedule"

        _LOGGER.debug("Setting schedule on %s: %s", url, event)
        response = await self.process_request(url=url, method="post", data=event)
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem setting schedule: %s", response)
            raise CommandFailedError(f"Problem setting schedule: {response}")

    async def delete_schedule(self, event_id: int) -> None:
        """Delete a schedule event by its ID.

        Sends 'DELETE /schedule/{event_id}'.

        Requires gateway firmware 4.0.0 or higher.

        :param event_id: Schedule event ID integer to delete.
        """
        self._require_firmware("4.0.0", "delete_schedule")

        if not isinstance(event_id, int) or isinstance(event_id, bool):
            raise TypeError("event_id must be an integer.")

        url = f"{self.url}schedule/{event_id}"
        _LOGGER.debug("Deleting schedule event %s on %s", event_id, url)
        response = await self.process_request(url=url, method="delete")
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem deleting schedule event %s: %s", event_id, response)
            raise CommandFailedError(
                f"Problem deleting schedule event {event_id}: {response}"
            )

    async def get_schedule_plan(self) -> Mapping[str, Any]:
        """Return the calculated schedule plan.

        Sends 'GET /schedule/plan'.

        Requires gateway firmware 4.1.0 or higher.

        :return: Schedule plan dictionary with current event, next event, and weekly instances.
        """
        self._require_firmware("4.1.0", "get_schedule_plan")

        url = f"{self.url}schedule/plan"
        _LOGGER.debug("Getting schedule plan from %s", url)
        response = await self.process_request(url=url, method="get")
        if not isinstance(response, Mapping):
            _LOGGER.error("Invalid response format for /schedule/plan: %s", response)
            raise CommandFailedError(
                f"Invalid response format for /schedule/plan: {response}"
            )

        return dict(response)
