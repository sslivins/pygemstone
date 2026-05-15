"""Typed exception hierarchy for pygemstone."""

from __future__ import annotations


class GemstoneError(Exception):
    """Base class for all pygemstone errors."""


class GemstoneAuthError(GemstoneError):
    """Raised when Cognito authentication or token refresh fails."""


class GemstoneConnectionError(GemstoneError):
    """Raised when the Gemstone cloud is unreachable or returns a transport error."""


class GemstoneApiError(GemstoneError):
    """Raised when the Gemstone API returns a non-success HTTP status.

    The :attr:`status` attribute carries the HTTP status code and
    :attr:`body` carries the (possibly truncated) response body for
    diagnostics. Authentication-related 401/403 are translated to
    :class:`GemstoneAuthError` instead.
    """

    def __init__(self, status: int, body: str, *, message: str | None = None) -> None:
        self.status = status
        self.body = body
        super().__init__(
            message or f"Gemstone API call failed: HTTP {status}: {body[:512]}"
        )


class GemstoneNotFoundError(GemstoneError):
    """Raised when the requested home group, device, or pattern cannot be found."""


class GemstoneValueError(GemstoneError, ValueError):
    """Raised when a property is set to an invalid value."""
