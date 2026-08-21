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
    CommandFailedError,
    FirmwareResolutionError,
    InvalidType,
    MissingMethod,
    MissingSerial,
    OpenEVSEError,
    ParseJSONError,
    UnknownError,
    UnknownStateError,
    UnsupportedFeature,
)
from .websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STARTING,
    STATE_STOPPED,
    OpenEVSEWebsocket,
)

__all__ = [
    "ERROR_TIMEOUT",
    "INFO_LOOP_RUNNING",
    "SIGNAL_CONNECTION_STATE",
    "STATE_CONNECTED",
    "STATE_DISCONNECTED",
    "STATE_STARTING",
    "STATE_STOPPED",
    "UPDATE_TRIGGERS",
    "AlreadyListening",
    "AuthenticationError",
    "CommandFailedError",
    "ContentTypeError",
    "FirmwareResolutionError",
    "InvalidType",
    "MissingMethod",
    "MissingSerial",
    "OpenEVSE",
    "OpenEVSEError",
    "OpenEVSEWebsocket",
    "ParseJSONError",
    "ServerTimeoutError",
    "UnknownError",
    "UnknownStateError",
    "UnsupportedFeature",
    "divert_mode",
    "states",
]
