"""Provide a package for python-openevse-http."""

# ruff: noqa: F401
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

from .client import (
    ERROR_TIMEOUT,
    INFO_LOOP_RUNNING,
    UPDATE_TRIGGERS,
    OpenEVSE,
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
    "ContentTypeError",
    "ERROR_TIMEOUT",
    "INFO_LOOP_RUNNING",
    "OpenEVSE",
    "OpenEVSEWebsocket",
    "SIGNAL_CONNECTION_STATE",
    "STATE_CONNECTED",
    "STATE_DISCONNECTED",
    "STATE_STOPPED",
    "ServerTimeoutError",
    "UPDATE_TRIGGERS",
    "AlreadyListening",
    "AuthenticationError",
    "InvalidType",
    "MissingMethod",
    "MissingSerial",
    "ParseJSONError",
    "UnknownError",
    "UnsupportedFeature",
    "divert_mode",
    "states",
]
