"""Websocket class for OpenEVSE HTTP."""

import asyncio
import datetime
import logging

import aiohttp  # type: ignore

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
        server,
        callback,
        user=None,
        password=None,
    ):
        """Initialize a OpenEVSEWebsocket instance."""
        self.session = aiohttp.ClientSession()
        self.uri = self._get_uri(server)
        self._user = user
        self._password = password
        self.callback = callback
        self._state = None
        self.failed_attempts = 0
        self._error_reason = None
        self._client = None
        self._ping = None
        self._pong = None

    @property
    def state(self):
        """Return the current state."""
        return self._state

    @state.setter
    async def state(self, value):
        """Set the state."""
        self._state = value
        _LOGGER.debug("Websocket %s", value)
        await self.callback(SIGNAL_CONNECTION_STATE, value, self._error_reason)
        self._error_reason = None

    @staticmethod
    def _get_uri(server):
        """Generate the websocket URI."""
        return server[: server.rfind("/")].replace("http", "ws") + "/ws"

    async def running(self):
        """Open a persistent websocket connection and act on events."""
        await OpenEVSEWebsocket.state.fset(self, STATE_STARTING)
        auth = None

        if self._user and self._password:
            auth = aiohttp.BasicAuth(self._user, self._password)

        try:
            async with self.session.ws_connect(
                self.uri,
                heartbeat=15,
                auth=auth,
            ) as ws_client:
                await OpenEVSEWebsocket.state.fset(self, STATE_CONNECTED)
                self.failed_attempts = 0
                self._client = ws_client

                async for message in ws_client:
                    if self.state == STATE_STOPPED:
                        break

                    if message.type == aiohttp.WSMsgType.TEXT:
                        msg = message.json()
                        msgtype = "data"
                        await self.callback(msgtype, msg, None)
                        if "pong" in msg.keys():
                            self._pong = datetime.datetime.now()

                    elif message.type == aiohttp.WSMsgType.CLOSED:
                        _LOGGER.warning("Websocket connection closed")
                        break

                    elif message.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error("Websocket error")
                        break

        except aiohttp.ClientResponseError as error:
            if error.status == 401:
                _LOGGER.error("Credentials rejected: %s", error)
                self._error_reason = ERROR_AUTH_FAILURE
            else:
                _LOGGER.error("Unexpected response received: %s", error)
                self._error_reason = error
            await OpenEVSEWebsocket.state.fset(self, STATE_STOPPED)
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
            if self.failed_attempts > MAX_FAILED_ATTEMPTS:
                self._error_reason = ERROR_TOO_MANY_RETRIES
                await OpenEVSEWebsocket.state.fset(self, STATE_STOPPED)
            elif self.state != STATE_STOPPED:
                retry_delay = min(2 ** (self.failed_attempts - 1) * 30, 300)
                self.failed_attempts += 1
                _LOGGER.error(
                    "Websocket connection failed, retrying in %ds: %s",
                    retry_delay,
                    error,
                )
                await OpenEVSEWebsocket.state.fset(self, STATE_DISCONNECTED)
                await asyncio.sleep(retry_delay)
        except Exception as error:  # pylint: disable=broad-except
            if self.state != STATE_STOPPED:
                _LOGGER.exception("Unexpected exception occurred: %s", error)
                self._error_reason = error
                await OpenEVSEWebsocket.state.fset(self, STATE_STOPPED)
        else:
            if self.state != STATE_STOPPED:
                await OpenEVSEWebsocket.state.fset(self, STATE_DISCONNECTED)
                await asyncio.sleep(5)

    async def listen(self):
        """Start the listening websocket."""
        self.failed_attempts = 0
        while self.state != STATE_STOPPED:
            await self.running()

    async def close(self):
        """Close the listening websocket."""
        await OpenEVSEWebsocket.state.fset(self, STATE_STOPPED)
        await self.session.close()

    async def keepalive(self):
        """Send ping requests to websocket."""
        if self._ping and self._pong:
            time_delta = self._pong - self._ping
            if time_delta < 0:
                # Negitive time should indicate no pong reply so consider the
                # websocket disconnected.
                self._error_reason = ERROR_PING_TIMEOUT
                await OpenEVSEWebsocket.state.fset(self, STATE_DISCONNECTED)

        data = {"ping": 1}
        _LOGGER.debug("Sending message: %s to websocket.", data)
        try:
            await self._client.send_json(data)
            self._ping = datetime.datetime.now()
            _LOGGER.debug("Ping message sent.")
        except TypeError as err:
            _LOGGER.error("Attempt to send ping data failed: %s", err)
        except ValueError as err:
            _LOGGER.error("Error parsing data: %s", err)
        except RuntimeError as err:
            _LOGGER.debug("Websocket connection issue: %s", err)
            await OpenEVSEWebsocket.state.fset(self, STATE_DISCONNECTED)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Problem sending ping request: %s", err)
            await OpenEVSEWebsocket.state.fset(self, STATE_DISCONNECTED)
