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

    def __init__(
        self,
        message_or_feature: str | None = None,
        min_version: str | None = None,
        component: str = "gateway",
    ) -> None:
        """Initialize UnsupportedFeature with optional structured parameters."""
        if min_version is not None and message_or_feature is not None:
            msg = f"{message_or_feature} requires {component} firmware {min_version} or higher."
        else:
            msg = message_or_feature or "Feature not supported for older firmware."
        super().__init__(msg)


class InvalidType(OpenEVSEError):
    """Exception for invalid types."""


class CommandFailedError(OpenEVSEError):
    """Exception for command rejections or failures."""


class UnknownStateError(OpenEVSEError):
    """Exception when charger state cannot be determined."""


class FirmwareResolutionError(OpenEVSEError):
    """Exception when firmware download URL cannot be resolved."""
