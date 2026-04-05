"""Core client class for python-openevse-http."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import threading
from collections.abc import Callable
from typing import Any

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from awesomeversion import AwesomeVersion
from awesomeversion.exceptions import AwesomeVersionCompareException

from .commands import CommandsMixin
from .const import (
    ERROR_TIMEOUT,
    UPDATE_TRIGGERS,
)
from .exceptions import (
    AlreadyListening,
    AuthenticationError,
    MissingMethod,
    MissingSerial,
    ParseJSONError,
)
from .managers import ManagersMixin
from .properties import PropertiesMixin
from .sensors import SensorsMixin
from .websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STOPPED,
    OpenEVSEWebsocket,
)

_LOGGER = logging.getLogger(__name__)


class OpenEVSE(CommandsMixin, ManagersMixin, SensorsMixin, PropertiesMixin):
    """Represent an OpenEVSE charger."""

    def __init__(
        self,
        host: str,
        user: str = "",
        pwd: str = "",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Connect to an OpenEVSE charger equipped with wifi or ethernet."""
        self._user = user
        self._pwd = pwd
        self.url = f"http://{host}/"
        self._status: dict = {}
        self._config: dict = {}
        self._override = None
        self._ws_listening = False
        self.websocket: OpenEVSEWebsocket | None = None
        self.callback: Callable | None = None
        self._loop = None
        self.tasks = None
        self._session = session
        self._session_external = session is not None

    async def process_request(
        self,
        url: str,
        method: str = "",
        data: Any = None,
        rapi: Any = None,
    ) -> dict[str, str] | dict[str, Any]:
        """Return result of processed HTTP request."""
        auth = None
        if method is None:
            raise MissingMethod

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
                    method.lower() != "get"
                    and isinstance(message, dict)
                    and any(key in message for key in UPDATE_TRIGGERS)
                ):
                    await self.update()
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

    async def update(self) -> None:
        """Update the values."""
        # TODO: add addiontal endpoints to update
        urls = [f"{self.url}config"]

        if not self._ws_listening:
            urls = [f"{self.url}status", f"{self.url}config"]

        for url in urls:
            _LOGGER.debug("Updating data from %s", url)
            response = await self.process_request(url, method="get")
            if "/status" in url:
                self._status = response
                _LOGGER.debug("Status update: %s", self._status)

            else:
                self._config = response
                _LOGGER.debug("Config update: %s", self._config)

    async def test_and_get(self) -> dict:
        """Test connection.

        Return model serial number as dict
        """
        url = f"{self.url}config"
        data = {}

        response = await self.process_request(url, method="get")
        if "wifi_serial" in response:
            serial = response["wifi_serial"]
        else:
            _LOGGER.debug("Older firmware detected, missing serial.")
            raise MissingSerial
        if "buildenv" in response:
            model = response["buildenv"]
        else:
            model = "unknown"

        data = {"serial": serial, "model": model}
        return data

    def ws_start(self) -> None:
        """Start the websocket listener."""
        if not self.websocket:
            self.websocket = OpenEVSEWebsocket(
                self.url, self._update_status, self._user, self._pwd, self._session
            )

        if self.websocket:
            if self._ws_listening and self.websocket.state == "connected":
                raise AlreadyListening
            if self._ws_listening and self.websocket.state != "connected":
                self._ws_listening = False
        self._start_listening()

    def _start_listening(self):
        """Start the websocket listener."""
        new_loop = False
        if not self._loop:
            try:
                _LOGGER.debug("Attempting to find running loop...")
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                new_loop = True
                _LOGGER.debug("Using new event loop...")

        if not self._ws_listening:
            _LOGGER.debug("Setting up websocket ping...")
            self._loop.create_task(self.websocket.listen())
            self._loop.create_task(self.repeat(300, self.websocket.keepalive))
            self._ws_listening = True

            if new_loop:
                threading.Thread(target=self._loop.run_forever, daemon=True).start()

    async def _update_status(self, msgtype, data, error):
        """Update data from websocket listener."""
        if msgtype == SIGNAL_CONNECTION_STATE:
            if data == STATE_CONNECTED:
                _LOGGER.debug("Websocket to %s successful", self.websocket.uri)
                self._ws_listening = True
            elif data == STATE_DISCONNECTED:
                _LOGGER.debug(
                    "Websocket to %s disconnected, retrying",
                    self.websocket.uri,
                )
                _LOGGER.debug("Disconnect message: %s", error)
                self._ws_listening = False

            # Stopped websockets without errors are expected during shutdown
            # and ignored
            elif data == STATE_STOPPED and error:
                _LOGGER.debug(
                    "Websocket to %s failed, aborting [Error: %s]",
                    self.websocket.uri,
                    error,
                )
                self._ws_listening = False

        elif msgtype == "data":
            _LOGGER.debug("Websocket data: %s", data)
            keys = data.keys()
            if "wh" in keys:
                data["watthour"] = data.pop("wh")
            # TODO: update specific endpoints based on _version prefix
            if any(key in keys for key in UPDATE_TRIGGERS):
                await self.update()
            self._status.update(data)

            if self.callback is not None:
                if self.is_coroutine_function(self.callback):
                    await self.callback()  # pylint: disable=not-callable
                else:
                    self.callback()  # pylint: disable=not-callable

    async def ws_disconnect(self) -> None:
        """Disconnect the websocket listener."""
        self._ws_listening = False
        if self.websocket is None:
            return
        await self.websocket.close()
        self.websocket = None

    def is_coroutine_function(self, callback):
        """Check if a callback is a coroutine function."""
        return inspect.iscoroutinefunction(callback)

    @property
    def ws_state(self) -> Any | None:
        """Return the status of the websocket listener."""
        if self.websocket is None:
            return None
        return self.websocket.state

    async def repeat(self, interval, func, *args, **kwargs):
        """Run func every interval seconds.

        If func has not finished before *interval*, will run again
        immediately when the previous iteration finished.

        *args and **kwargs are passed as the arguments to func.
        """
        while self.ws_state != "stopped":
            await asyncio.sleep(interval)
            await func(*args, **kwargs)

    def _version_check(self, min_version: str, max_version: str = "") -> bool:
        """Return bool if minimum version is met."""
        if "version" not in self._config:
            # Throw warning if we can't find the version
            _LOGGER.warning("Unable to find firmware version.")
            return False
        cutoff = AwesomeVersion(min_version)
        current = ""
        limit = ""
        if max_version != "":
            limit = AwesomeVersion(max_version)

        firmware_filtered = None
        firmware_search = re.search(r"\d+\.\d+\.\d+", self._config["version"])
        if firmware_search:
            firmware_filtered = firmware_search.group(0)
        else:
            _LOGGER.warning(
                "Non-standard versioning string: %s", self._config["version"]
            )

        _LOGGER.debug("Detected firmware: %s", self._config["version"])
        _LOGGER.debug("Filtered firmware: %s", firmware_filtered)

        if "dev" in self._config["version"]:
            value = self._config["version"]
            _LOGGER.debug("Stripping 'dev' from version.")
            value = value.split(".")
            value = ".".join(value[0:3])
        elif "master" in self._config["version"]:
            value = "dev"
        else:
            value = firmware_filtered

        current = AwesomeVersion(value)

        if limit:
            try:
                if cutoff <= current <= limit:
                    return True
            except AwesomeVersionCompareException:
                _LOGGER.debug("Non-semver firmware version detected.")
            return False

        try:
            if current >= cutoff:
                return True
        except AwesomeVersionCompareException:
            _LOGGER.debug("Non-semver firmware version detected.")
        return False

    def version_check(self, min_version: str, max_version: str = "") -> bool:
        """Unprotected function call for version checking."""
        return self._version_check(min_version=min_version, max_version=max_version)
