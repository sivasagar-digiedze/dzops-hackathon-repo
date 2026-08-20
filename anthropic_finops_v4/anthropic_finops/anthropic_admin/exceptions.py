"""
Exception hierarchy for the Anthropic Admin API client.

None of these ever include the API key — it only ever travels in the
`x-api-key` header, never in a URL, query string, or exception message.
"""
from __future__ import annotations

from typing import Any, Optional


class AnthropicAdminError(Exception):
    """Base class for all errors raised by this integration."""


class AnthropicAPIError(AnthropicAdminError):
    """Raised for any non-2xx HTTP response from the Admin API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        endpoint: str,
        error_type: Optional[str] = None,
        request_id: Optional[str] = None,
        raw_body: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.endpoint = endpoint
        self.error_type = error_type
        self.request_id = request_id
        self.raw_body = raw_body

    def to_structured_error(self, *, component: Optional[str] = None) -> dict:
        """Structured, log/output-safe representation (no secrets)."""
        return {
            "component": component or self.endpoint,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "type": self.error_type or "api_error",
            "message": self.message,
            "request_id": self.request_id,
        }


class AuthenticationError(AnthropicAPIError):
    """401 — invalid or revoked Admin API key. Never retried."""


class PermissionDeniedError(AnthropicAPIError):
    """403 — key lacks the scope/role required for this endpoint."""


class NotFoundError(AnthropicAPIError):
    """404 — resource or endpoint not available for this org/plan."""


class InvalidRequestError(AnthropicAPIError):
    """400/409/422 — the request itself was malformed. Never retried."""


class RateLimitError(AnthropicAPIError):
    """429 — caller is being rate limited. Retryable with backoff."""

    def __init__(self, *args: Any, retry_after_seconds: Optional[float] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class ServerError(AnthropicAPIError):
    """5xx / timeout / transport failure. Retryable with backoff."""


class UnsupportedEndpointError(AnthropicAdminError):
    """
    Raised internally when an endpoint is known ahead of time not to
    apply to this organization type (used by spend_limits). Collector
    catches this and records it as a capability=false, not a fatal error.
    """

    def __init__(self, message: str, *, endpoint: str) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.message = message


class PaginationError(AnthropicAdminError):
    """Raised when a paginated response is malformed or loops."""
