"""Backwork Python SDK - Medicare coverage policies and prior authorization."""

from .client import BackworkClient, VerityClient
from .exceptions import (
    BackworkError,
    VerityError,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    RateLimitError,
)

__version__ = "1.0.0"
__all__ = [
    "BackworkClient",
    "BackworkError",
    "AuthenticationError",
    "ValidationError",
    "NotFoundError",
    "RateLimitError",
    # Pre-rename aliases, exported so `from backwork import VerityClient` keeps
    # working for callers mid-migration. Drop with the aliases themselves.
    "VerityClient",
    "VerityError",
]
