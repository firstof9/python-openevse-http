"""Provide a package for python-openevse-http."""

# ruff: noqa: F401
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

from .client import (
    OpenEVSE,
)
from .const import (
    ERROR_TIMEOUT,
    INFO_LOOP_RUNNING,
    UPDATE_TRIGGERS,
    divert_mode,
    states,
)
from .exceptions import (
    AlreadyListening,
    AuthenticationError,
    InvalidType,
    MissingMethod,
    MissingSerial,
    ParseJSONError,
    UnknownError,
    UnsupportedFeature,
)
from .websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STOPPED,
    OpenEVSEWebsocket,
)

__all__ = [
    "AlreadyListening",
    "AuthenticationError",
    "ContentTypeError",
    "ERROR_TIMEOUT",
    "INFO_LOOP_RUNNING",
    "InvalidType",
    "MissingMethod",
    "MissingSerial",
    "OpenEVSE",
    "OpenEVSEWebsocket",
    "ParseJSONError",
    "SIGNAL_CONNECTION_STATE",
    "STATE_CONNECTED",
    "STATE_DISCONNECTED",
    "STATE_STOPPED",
    "ServerTimeoutError",
    "UPDATE_TRIGGERS",
    "UnknownError",
    "UnsupportedFeature",
    "divert_mode",
    "states",
]
