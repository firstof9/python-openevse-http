"""Requester class for OpenEVSE HTTP."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
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
        self._update_callback: Callable[[], Awaitable[None]] | None = None
        self._invoking_callback = False
        self._pending_refresh = False

    def set_update_callback(
        self, callback: Callable[[], Awaitable[None]] | None
    ) -> None:
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
                if resp.status >= 400:
                    _LOGGER.warning("HTTP Error %s: %s", resp.status, message)
                    if isinstance(message, dict):
                        message.update({"ok": False, "status": resp.status})
                    else:
                        message = {"msg": message, "ok": False, "status": resp.status}
                    return message

                if (
                    method == "post"
                    and isinstance(message, dict)
                    and "config_version" in message
                    and self._update_callback
                ):
                    if self._invoking_callback:
                        self._pending_refresh = True
                    else:
                        self._invoking_callback = True
                        try:
                            while True:
                                self._pending_refresh = False
                                try:
                                    await self._update_callback()
                                except Exception as err:  # pylint: disable=broad-exception-caught
                                    _LOGGER.exception(
                                        "Exception during write-refresh: %s", err
                                    )
                                if not self._pending_refresh:
                                    break
                        finally:
                            self._invoking_callback = False
                return message

        except (TimeoutError, ServerTimeoutError):
            _LOGGER.error("%s: %s", ERROR_TIMEOUT, url)
            raise
        except ContentTypeError as err:
            _LOGGER.error("Content error: %s", err.message)
            raise

    async def send_command(self, command: str) -> tuple | dict:
        """Send a RAPI command to the charger and parses the response."""
        url = f"{self.url}r"
        data = {"json": 1, "rapi": command}

        _LOGGER.debug("Posting data: %s to %s", command, url)
        value = await self.process_request(url=url, method="post", rapi=data)
        if isinstance(value, dict) and value.get("ok") is False:
            return value

        cmd = value.get("cmd", command)
        if "ret" not in value:
            return (cmd, value.get("msg", ""))
        return (cmd, value["ret"])
