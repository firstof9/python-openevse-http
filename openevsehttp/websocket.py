"""Websocket class for OpenEVSE HTTP."""

from __future__ import annotations

import asyncio
import datetime
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5

ERROR_AUTH_FAILURE = "Authorization failure"
ERROR_TOO_MANY_RETRIES = "Too many retries"
ERROR_UNKNOWN = "Unknown"
ERROR_PING_TIMEOUT = "No pong reply"

SIGNAL_CONNECTION_STATE = "websocket_state"
STATE_CONNECTED = "connected"
STATE_DISCONNECTED = "disconnected"
STATE_STARTING = "starting"
STATE_STOPPED = "stopped"


class OpenEVSEWebsocket:
    """Represent a websocket connection to a OpenEVSE charger."""

    def __init__(
        self,
        server: str,
        callback: Callable[[str, Any, Any], Any] | None,
        user: str | None = None,
        password: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize a OpenEVSEWebsocket instance."""
        self.session = session
        self._session_external = session is not None
        self.uri = self._get_uri(server)
        self._user = user
        self._password = password
        self.callback = callback
        self._state = STATE_DISCONNECTED
        self.failed_attempts = 0
        self._error_reason: Any = None
        self._client: aiohttp.ClientWebSocketResponse | None = None
        self._ping: datetime.datetime | None = None
        self._pong: datetime.datetime | None = None
        self._tasks: set[asyncio.Task[Any]] = set()
        self._listener_loop: asyncio.AbstractEventLoop | None = None

    @property
    def state(self) -> str:
        """Return the current state."""
        return self._state

    @state.setter
    def state(self, value: str) -> None:
        """Setter that schedules the callback."""
        self._state = value
        _LOGGER.debug("Websocket %s", value)

        if not self.callback:
            self._error_reason = None
            return

        # Prepare the coroutine or invoke the callback
        coro = self.callback(SIGNAL_CONNECTION_STATE, value, self._error_reason)

        if not inspect.isawaitable(coro):
            self._error_reason = None
            return

        try:
            if self._listener_loop:
                self._listener_loop.call_soon_threadsafe(self._schedule_task, coro)
            else:
                try:
                    task = asyncio.ensure_future(coro)
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
                except RuntimeError:
                    # Fallback to get_event_loop if ensure_future fails and no _listener_loop
                    loop = asyncio.get_event_loop()
                    loop.call_soon_threadsafe(self._schedule_task, coro)
        except RuntimeError:
            _LOGGER.error("Failed to schedule callback from sync context: %s", coro)
            if hasattr(coro, "close"):
                coro.close()
        self._error_reason = None

    def _schedule_task(self, coro: Awaitable[Any]) -> None:
        """Schedule a task from a thread-safe context."""
        try:
            task = asyncio.ensure_future(coro)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        except RuntimeError:
            _LOGGER.error("Failed to schedule callback task: %s", coro)
            # If we still can't schedule it, we must at least close the coroutine
            # to avoid RuntimeWarning: coroutine '...' was never awaited
            if hasattr(coro, "close"):
                coro.close()

    async def _set_state(self, value: str) -> None:
        """Async helper to set the state and await the callback."""
        self._state = value
        _LOGGER.debug("Websocket %s", value)
        if self.callback:
            result = self.callback(SIGNAL_CONNECTION_STATE, value, self._error_reason)
            if inspect.isawaitable(result):
                await result
        self._error_reason = None

    @staticmethod
    def _get_uri(server: str) -> str:
        """Generate the websocket URI."""
        return server[: server.rfind("/")].replace("http", "ws") + "/ws"

    async def running(self) -> None:
        """Open a persistent websocket connection and act on events."""
        await self._ensure_session()
        await self._set_state(STATE_STARTING)
        auth = None

        if self._user and self._password:
            auth = aiohttp.BasicAuth(self._user, self._password)

        try:
            assert self.session is not None
            async with self.session.ws_connect(
                self.uri,
                heartbeat=15,
                auth=auth,
            ) as ws_client:
                self._client = ws_client
                await self._set_state(STATE_CONNECTED)
                self.failed_attempts = 0
                await self._handle_messages(ws_client)

        except aiohttp.ClientResponseError as error:
            await self._handle_response_error(error)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
            await self._handle_connection_error(error)
        except Exception as error:  # pylint: disable=broad-except
            if self.state != STATE_STOPPED:
                _LOGGER.exception("Unexpected exception occurred: %s", error)
                self._error_reason = error
                await self._set_state(STATE_STOPPED)
        else:
            if self.state != STATE_STOPPED:
                await self._set_state(STATE_DISCONNECTED)
                await asyncio.sleep(5)
        finally:
            if self._client is not None:
                await self._client.close()
                self._client = None

    async def _handle_messages(
        self, ws_client: aiohttp.ClientWebSocketResponse
    ) -> None:
        """Handle incoming websocket messages."""
        async for message in ws_client:
            if self.state == STATE_STOPPED:
                break

            if message.type == aiohttp.WSMsgType.TEXT:
                msg = message.json()
                if isinstance(msg, dict) and "pong" in msg:
                    self._pong = datetime.datetime.now()
                    if len(msg) == 1:
                        # Pure pong frame, skip callback
                        continue

                msgtype = "data"
                if self.callback:
                    result = self.callback(msgtype, msg, None)
                    if inspect.isawaitable(result):
                        await result

            elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                if message.type == aiohttp.WSMsgType.CLOSED:
                    _LOGGER.warning("Websocket connection closed")
                else:
                    _LOGGER.error("Websocket error")
                break

    async def _handle_response_error(self, error: aiohttp.ClientResponseError) -> None:
        """Handle ClientResponseError."""
        if error.status == 401:
            _LOGGER.error("Credentials rejected: %s", error)
            self._error_reason = ERROR_AUTH_FAILURE
        else:
            _LOGGER.error("Unexpected response received: %s", error)
            self._error_reason = error
        await self._set_state(STATE_STOPPED)

    async def _handle_connection_error(self, error: BaseException) -> None:
        """Handle connection errors."""
        self.failed_attempts += 1
        if self.failed_attempts > MAX_FAILED_ATTEMPTS:
            self._error_reason = ERROR_TOO_MANY_RETRIES
            await self._set_state(STATE_STOPPED)
        elif self.state != STATE_STOPPED:
            retry_delay = min(2 ** (self.failed_attempts - 1) * 30, 300)
            _LOGGER.error(
                "Websocket connection failed, retrying in %ds: %s",
                retry_delay,
                error,
            )
            await self._set_state(STATE_DISCONNECTED)
            await asyncio.sleep(retry_delay)

    async def listen(self) -> None:
        """Start the listening websocket."""
        await self._ensure_session()
        self.failed_attempts = 0
        self._listener_loop = asyncio.get_running_loop()
        try:
            while self.state != STATE_STOPPED:
                await self.running()
        finally:
            self._listener_loop = None

    async def _ensure_session(self) -> None:
        """Ensure aiohttp.ClientSession exists."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._session_external = False

    async def close(self) -> None:
        """Close the listening websocket."""
        await self._set_state(STATE_STOPPED)

        if self._tasks:
            for task in self._tasks:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        if self._client is not None:
            await self._client.close()
            self._client = None
        # Only close the session if we created it
        if not self._session_external and self.session is not None:
            await self.session.close()
            self.session = None

    async def keepalive(self) -> None:
        """Send ping requests to websocket."""
        if self._ping and self._pong:
            time_delta = self._pong - self._ping
            if time_delta < datetime.timedelta(0):
                # Negative time should indicate no pong reply so consider the
                # websocket disconnected.
                self._error_reason = ERROR_PING_TIMEOUT
                await self._set_state(STATE_DISCONNECTED)

        data = {"ping": 1}
        _LOGGER.debug("Sending message: %s to websocket.", data)
        try:
            if self._client:
                await self._client.send_json(data)
                self._ping = datetime.datetime.now()
                _LOGGER.debug("Ping message sent.")
            else:
                _LOGGER.warning("Websocket client not found.")
        except TypeError as err:
            _LOGGER.error("Attempt to send ping data failed: %s", err)
        except ValueError as err:
            _LOGGER.error("Error parsing data: %s", err)
        except RuntimeError as err:
            _LOGGER.debug("Websocket connection issue: %s", err)
            await self._set_state(STATE_DISCONNECTED)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Problem sending ping request: %s", err)
            await self._set_state(STATE_DISCONNECTED)
