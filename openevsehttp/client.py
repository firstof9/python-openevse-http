"""Core client class for python-openevse-http."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import threading
from collections.abc import Callable, Mapping
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
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws_listen_task: asyncio.Task | None = None
        self._ws_keepalive_task: asyncio.Task | None = None
        self._owns_loop = False
        self._loop_thread: threading.Thread | None = None
        self._session = session
        self._session_external = session is not None

    async def process_request(
        self,
        url: str,
        method: str = "",
        data: Any = None,
        rapi: Any = None,
    ) -> Mapping[str, Any] | list[Any] | str:
        """Return result of processed HTTP request."""
        auth = None
        allowed_methods = ["get", "post", "put", "delete", "patch", "head", "options"]
        if method not in allowed_methods:
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

    def _normalize_response(self, response: Any) -> dict[str, Any] | list[Any]:
        """Normalize response to a dict or list."""
        if isinstance(response, dict | list):
            return response
        _LOGGER.debug("Normalizing non-json response: %s", response)
        return {"msg": response}

    async def _process_request_with_session(
        self,
        session: aiohttp.ClientSession,
        url: str,
        method: str,
        data: Any,
        rapi: Any,
        auth: Any,
    ) -> Mapping[str, Any] | list[Any] | str:
        """Process a request with a given session."""
        if not hasattr(session, method):
            raise MissingMethod
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
        if not isinstance(value, Mapping) or "ret" not in value or "cmd" not in value:
            if isinstance(value, Mapping) and "msg" in value:
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
                if isinstance(response, Mapping) and "error" not in response:
                    self._status = dict(response)
                    _LOGGER.debug("Status update: %s", self._status)
                elif isinstance(response, Mapping):
                    _LOGGER.warning(
                        "Error in /status response: %s", response.get("error")
                    )
                else:
                    _LOGGER.warning(
                        "Received non-JSON response from /status: %s", response
                    )

            else:
                if isinstance(response, Mapping) and "error" not in response:
                    self._config = dict(response)
                    _LOGGER.debug("Config update: %s", self._config)
                elif isinstance(response, Mapping):
                    _LOGGER.warning(
                        "Error in /config response: %s", response.get("error")
                    )
                else:
                    _LOGGER.warning(
                        "Received non-JSON response from /config: %s", response
                    )

    async def test_and_get(self) -> dict:
        """Test connection.

        Return model serial number as dict
        """
        url = f"{self.url}config"
        data = {}

        response = await self.process_request(url, method="get")
        if not isinstance(response, Mapping):
            _LOGGER.debug("Invalid response from config: %s", response)
            raise MissingSerial

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
        if self.websocket and self.websocket.state != STATE_STOPPED:
            raise AlreadyListening

        # Detect loop mismatch
        use_session = self._session
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # We are about to create a private loop in _start_listening
            # If we have a session, it's likely bound to another loop
            if self._session:
                _LOGGER.warning(
                    "Caller-provided session may not work on private event loop. "
                    "Creating a loop-local session."
                )
                use_session = None
                # Clear self._session so subsequent await self.update() uses
                # a loop-local session as well.
                self._session = None
                self._session_external = False

        if not self.websocket or self.websocket.state == STATE_STOPPED:
            self.websocket = OpenEVSEWebsocket(
                self.url, self._update_status, self._user, self._pwd, use_session
            )

        self._start_listening()

    def _start_listening(self):
        """Start the websocket listener."""
        if not self._loop:
            try:
                _LOGGER.debug("Attempting to find running loop...")
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                self._owns_loop = True
                _LOGGER.debug("Using new event loop...")

        if not self._ws_listening and self.websocket is not None:
            _LOGGER.debug("Setting up websocket tasks...")
            self._ws_listen_task = self._loop.create_task(self.websocket.listen())
            self._ws_keepalive_task = self._loop.create_task(
                self.repeat(300, self.websocket.keepalive)
            )

            if self._owns_loop:
                self._loop_thread = threading.Thread(
                    target=self._loop.run_forever, daemon=True
                )
                self._loop_thread.start()

    async def _update_status(self, msgtype, data, error):
        """Update data from websocket listener."""
        if msgtype == SIGNAL_CONNECTION_STATE:
            uri = self.websocket.uri if self.websocket else "Unknown"
            if data == STATE_CONNECTED:
                _LOGGER.debug("Websocket to %s successful", uri)
                self._ws_listening = True
            elif data == STATE_DISCONNECTED:
                _LOGGER.debug(
                    "Websocket to %s disconnected, retrying",
                    uri,
                )
                _LOGGER.debug("Disconnect message: %s", error)
                self._ws_listening = False

            # Stopped websockets without errors are expected during shutdown
            # and ignored
            elif data == STATE_STOPPED and error:
                _LOGGER.debug(
                    "Websocket to %s failed, aborting [Error: %s]",
                    uri,
                    error,
                )
                self._ws_listening = False

        elif msgtype == "data":
            _LOGGER.debug("Websocket data: %s", data)
            if not isinstance(data, Mapping):
                _LOGGER.warning("Received non-Mapping websocket data: %s", data)
                return

            keys = data.keys()
            if "wh" in keys:
                data["watthour"] = data.pop("wh")
            # TODO: update specific endpoints based on _version prefix
            if any(key in keys for key in UPDATE_TRIGGERS):
                await self.update()
            self._status.update(data)

            if self.callback is not None:
                result = self.callback()  # pylint: disable=not-callable
                if inspect.isawaitable(result):
                    await result

    async def _shutdown(self):
        """Shutdown the websocket and tasks on the listener loop."""
        tasks = []
        if self._ws_keepalive_task:
            self._ws_keepalive_task.cancel()
            tasks.append(self._ws_keepalive_task)
        if self._ws_listen_task:
            self._ws_listen_task.cancel()
            tasks.append(self._ws_listen_task)

        if self.websocket:
            # Close the websocket (this cancels running() internal tasks)
            await self.websocket.close()

            # Cancel any remaining callback tasks
            for task in list(self.websocket._tasks):
                if not task.done():
                    task.cancel()
                    tasks.append(task)
            self.websocket._tasks.clear()

        if tasks:
            await asyncio.gather(
                *(t for t in tasks if isinstance(t, asyncio.Future | asyncio.Task)),
                return_exceptions=True,
            )

        if self.websocket:
            self.websocket = None

        self._ws_listen_task = None
        self._ws_keepalive_task = None
        if self._owns_loop and self._loop:
            self._loop.stop()

    async def ws_disconnect(self) -> None:
        """Disconnect the websocket listener."""
        self._ws_listening = False

        if self._owns_loop and self._loop:
            # Schedule shutdown coroutine on the loop thread
            future = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
            shutdown_succeeded = False
            try:
                # Wait for the shutdown to complete on the other loop
                await asyncio.wait_for(asyncio.wrap_future(future), timeout=2.0)
                shutdown_succeeded = True
            except (TimeoutError, asyncio.CancelledError) as err:
                _LOGGER.debug("Error during shutdown coroutine: %s", err)

            if self._loop_thread:
                await asyncio.to_thread(self._loop_thread.join, 2.0)
                if not self._loop_thread.is_alive():
                    self._loop_thread = None

            if shutdown_succeeded and self._loop_thread is None:
                self._loop.close()
                self._loop = None
                self._owns_loop = False
        else:
            # Standard async disconnect for caller loop
            await self._shutdown()

    def is_coroutine_function(self, callback):
        """Check if a callback is a coroutine function."""
        return inspect.iscoroutinefunction(callback)

    @property
    def ws_state(self) -> Any | None:
        """Return the status of the websocket listener."""
        if self.websocket is None:
            return STATE_STOPPED
        return self.websocket.state

    async def repeat(self, interval, func, *args, **kwargs):
        """Run func every interval seconds.

        If func has not finished before *interval*, will run again
        immediately when the previous iteration finished.

        *args and **kwargs are passed as the arguments to func.
        """
        while self.ws_state != STATE_STOPPED and self._ws_listening:
            await asyncio.sleep(interval)
            if self.ws_state == STATE_STOPPED or not self._ws_listening:
                break
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                await result

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

        if firmware_filtered is None:
            _LOGGER.warning(
                "Non-standard versioning string: %s", self._config["version"]
            )
            _LOGGER.debug("Non-semver firmware version detected.")
            return False

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
                if cutoff <= current < limit:
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
