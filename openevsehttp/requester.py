"""Requester class for OpenEVSE HTTP."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

from .const import ERROR_TIMEOUT
from .exceptions import (
    AuthenticationError,
    MissingMethod,
    ParseJSONError,
)

_LOGGER = logging.getLogger(__name__)


class Requester:
    """Handle HTTP and RAPI requests to OpenEVSE."""

    def __init__(
        self,
        host: str,
        user: str = "",
        pwd: str = "",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the requester."""
        self._user = user
        self._pwd = pwd
        self.url = f"http://{host}/"
        self._session = session
        self._update_callback = None

    def set_update_callback(self, callback):
        """Set the update callback."""
        self._update_callback = callback

    async def process_request(
        self,
        url: str,
        method: str = "get",
        data: Any = None,
        rapi: Any = None,
    ) -> dict[str, str] | dict[str, Any]:
        """Return result of processed HTTP request."""
        auth = None
        allowed_methods = ["get", "post", "put", "delete", "patch", "head", "options"]
        if not isinstance(method, str) or method.lower() not in allowed_methods:
            raise MissingMethod
        method = method.lower()

        if self._user and self._pwd:
            auth = aiohttp.BasicAuth(self._user, self._pwd)

        # Use provided session or create a temporary one
        if (session := self._session) is None:
            async with aiohttp.ClientSession() as session:
                return await self._process_request_with_session(
                    session, url, method, data, rapi, auth
                )
        else:
            return await self._process_request_with_session(
                session, url, method, data, rapi, auth
            )

    async def _process_request_with_session(
        self,
        session: aiohttp.ClientSession,
        url: str,
        method: str,
        data: Any,
        rapi: Any,
        auth: Any,
    ) -> dict[str, str] | dict[str, Any]:
        """Process a request with a given session."""
        http_method = getattr(session, method)
        _LOGGER.debug(
            "Connecting to %s with data: %s rapi: %s using method %s",
            url,
            data,
            rapi,
            method,
        )
        try:
            kwargs = {"data": rapi, "auth": auth}
            if data is not None:
                kwargs["json"] = data
            async with http_method(url, **kwargs) as resp:
                try:
                    message = await resp.text()
                except UnicodeDecodeError:
                    _LOGGER.debug("Decoding error")
                    message = await resp.read()
                    message = message.decode(errors="replace")

                try:
                    message = json.loads(message)
                except ValueError:
                    _LOGGER.warning("Non JSON response: %s", message)
                    message = {"msg": message}

                if resp.status == 400:
                    if isinstance(message, dict) and "msg" in message:
                        _LOGGER.error("Error 400: %s", message["msg"])
                    elif isinstance(message, dict) and "error" in message:
                        _LOGGER.error("Error 400: %s", message["error"])
                    else:
                        _LOGGER.error("Error 400: %s", message)
                    raise ParseJSONError
                if resp.status == 401:
                    _LOGGER.error("Authentication error: %s", message)
                    raise AuthenticationError
                if resp.status in [404, 405, 500]:
                    _LOGGER.warning("%s", message)

                if (
                    method == "post"
                    and isinstance(message, dict)
                    and "config_version" in message
                    and self._update_callback
                ):
                    await self._update_callback()
                return message

        except (TimeoutError, ServerTimeoutError):
            _LOGGER.error("%s: %s", ERROR_TIMEOUT, url)
            raise
        except ContentTypeError as err:
            _LOGGER.error("Content error: %s", err.message)
            raise

    async def send_command(self, command: str) -> tuple:
        """Send a RAPI command to the charger and parses the response."""
        url = f"{self.url}r"
        data = {"json": 1, "rapi": command}

        _LOGGER.debug("Posting data: %s to %s", command, url)
        value = await self.process_request(url=url, method="post", rapi=data)
        if "ret" not in value:
            if "msg" in value:
                return (False, value["msg"])
            return (False, "")
        return (value["cmd"], value["ret"])
