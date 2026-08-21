"""Exceptions."""


class OpenEVSEError(Exception):
    """Base exception for python-openevse-http."""


class AuthenticationError(OpenEVSEError):
    """Exception for authentication errors."""


class ParseJSONError(OpenEVSEError):
    """Exception for JSON parsing errors."""


class UnknownError(OpenEVSEError):
    """Exception for Unknown errors."""


class MissingMethod(OpenEVSEError):
    """Exception for missing method variable."""


class AlreadyListening(OpenEVSEError):
    """Exception for already listening websocket."""


class MissingSerial(OpenEVSEError):
    """Exception for missing serial number."""


class UnsupportedFeature(OpenEVSEError):
    """Exception for firmware that is too old."""


class InvalidType(OpenEVSEError):
    """Exception for invalid types."""


class CommandFailedError(OpenEVSEError):
    """Exception for command rejections or failures."""


class UnknownStateError(OpenEVSEError):
    """Exception when charger state cannot be determined."""


class FirmwareResolutionError(OpenEVSEError):
    """Exception when firmware download URL cannot be resolved."""
