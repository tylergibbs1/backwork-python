"""Exceptions for Backwork SDK."""

from typing import Any, Dict, Optional


class BackworkError(Exception):
    """Base exception for all Backwork SDK errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.hint = hint
        self.details = details or {}


class AuthenticationError(BackworkError):
    """Raised when API key is missing or invalid."""

    pass


class ValidationError(BackworkError):
    """Raised when request parameters are invalid."""

    pass


class NotFoundError(BackworkError):
    """Raised when a resource is not found."""

    pass


class RateLimitError(BackworkError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        limit: Optional[int] = None,
        remaining: Optional[int] = None,
        reset: Optional[int] = None,
        **kwargs: Any,
    ):
        super().__init__(message, **kwargs)
        self.limit = limit
        self.remaining = remaining
        self.reset = reset


# Pre-rename alias. Existing `except VerityError:` blocks must keep catching the
# base error; this is the same class, not a subclass, so isinstance still holds.
# Safe to delete in the first major version after the rename ships.
VerityError = BackworkError
