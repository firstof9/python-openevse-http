"""Provide a package for python-openevse-http."""

from .client import OpenEVSE
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
    "InvalidType",
    "MissingMethod",
    "MissingSerial",
    "OpenEVSE",
    "ParseJSONError",
    "UnknownError",
    "UnsupportedFeature",
]
