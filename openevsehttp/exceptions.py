"""Exceptions."""


class AuthenticationError(Exception):
    """Exception for authentication errors."""


class ParseJSONError(Exception):
    """Exception for JSON parsing errors."""


class UnknownError(Exception):
    """Exception for Unknown errors."""


class MissingMethod(Exception):
    """Exception for missing method variable."""


class AlreadyListening(Exception):
    """Exception for already listening websocket."""
