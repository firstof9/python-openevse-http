"""Compatibility shim for python-openevse-http."""

from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

from .client import (
    INFO_LOOP_RUNNING,
    UPDATE_TRIGGERS,
    OpenEVSE,
    states,
)
from .client import (
    divert_mode_map as divert_mode,
)
from .const import ERROR_TIMEOUT
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
    "ParseJSONError",
    "ServerTimeoutError",
    "UnknownError",
    "UnsupportedFeature",
    "UPDATE_TRIGGERS",
    "divert_mode",
    "states",
]
