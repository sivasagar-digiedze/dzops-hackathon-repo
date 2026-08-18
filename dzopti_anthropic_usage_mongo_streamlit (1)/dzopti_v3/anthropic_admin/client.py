"""
Reusable async HTTP client for the Anthropic Admin API.

- One httpx.AsyncClient is created per AnthropicAdminClient instance and
  reused for its lifetime (connection pooling) — never recreated per call.
- 401/400/409/422 are never retried (bad credential or bad request).
- 429/5xx/timeouts are retried with exponential backoff + jitter, capped
  at max_retries, and Retry-After is respected when Anthropic sends it.
- Every log call's `extra` dict avoids Python logging's reserved
  LogRecord attribute names (message, args, levelname, msg, name, etc.)
  — see the module-level `_RESERVED_LOG_KEYS` guard used by `_safe_extra`.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Mapping, Optional

import httpx

from .config import AnthropicAdminConfig
from .exceptions import (
    AuthenticationError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    AnthropicAPIError,
)

logger = logging.getLogger("dzopti.anthropic_admin.client")

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_NEVER_RETRY_STATUS_CODES = {400, 401, 403, 404, 409, 422}

# Names reserved by Python's logging.LogRecord — never put these as keys
# inside an `extra={...}` dict, or logging raises "KeyError: Attempt to
# overwrite ... in LogRecord".
_RESERVED_LOG_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message",
}


def _safe_extra(**kwargs: Any) -> dict:
    """Build a logging `extra` dict, prefixing any reserved key so it never collides."""
    return {(f"ctx_{k}" if k in _RESERVED_LOG_KEYS else k): v for k, v in kwargs.items()}


class AnthropicAdminClient:
    """Thin, reusable async wrapper around authenticated Admin API HTTP calls."""

    def __init__(self, config: AnthropicAdminConfig) -> None:
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AnthropicAdminClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        if self._client is not None:
            return
        timeout = httpx.Timeout(
            timeout=self._config.request_timeout_seconds,
            connect=self._config.connect_timeout_seconds,
        )
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=timeout,
            headers=self._default_headers(),
        )
        logger.info("anthropic_admin.client_started", extra=_safe_extra(base_url=self._config.base_url))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("anthropic_admin.client_closed")

    def _default_headers(self) -> dict:
        # x-api-key is the ONLY place the secret is ever placed.
        return {
            "x-api-key": self._config.admin_api_key,
            "anthropic-version": self._config.anthropic_version,
            "content-type": "application/json",
            "user-agent": self._config.user_agent,
        }

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "AnthropicAdminClient is not started. Use "
                "'async with AnthropicAdminClient(config) as client:' "
                "or call await client.start() first."
            )
        return self._client

    async def get(self, path: str, *, params: Optional[Mapping[str, Any]] = None) -> dict:
        return await self._request_with_retries("GET", path, params=params)

    async def _request_with_retries(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
    ) -> dict:
        attempt = 0
        last_error: Optional[AnthropicAPIError] = None

        while attempt <= self._config.max_retries:
            attempt += 1
            started = time.monotonic()
            try:
                response = await self._http.request(method, path, params=params)
            except httpx.TimeoutException as exc:
                logger.warning(
                    "anthropic_admin.request_timeout",
                    extra=_safe_extra(endpoint=path, attempt=attempt, method=method),
                )
                last_error = ServerError(
                    f"Timed out calling Anthropic Admin API: {exc}",
                    status_code=0, endpoint=path, error_type="timeout",
                )
                await self._sleep_before_retry(attempt, retry_after=None)
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "anthropic_admin.transport_error",
                    extra=_safe_extra(endpoint=path, attempt=attempt, method=method),
                )
                last_error = ServerError(
                    f"Transport error calling Anthropic Admin API: {exc}",
                    status_code=0, endpoint=path, error_type="transport_error",
                )
                await self._sleep_before_retry(attempt, retry_after=None)
                continue

            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            logger.info(
                "anthropic_admin.response",
                extra=_safe_extra(
                    endpoint=path, method=method, status_code=response.status_code,
                    attempt=attempt, elapsed_ms=elapsed_ms,
                ),
            )

            if response.status_code < 300:
                return response.json() if response.content else {}

            error = self._build_error(response, path)

            if response.status_code in _NEVER_RETRY_STATUS_CODES:
                raise error

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt <= self._config.max_retries:
                retry_after = self._parse_retry_after(response)
                logger.warning(
                    "anthropic_admin.retryable_error",
                    extra=_safe_extra(
                        endpoint=path, status_code=response.status_code,
                        attempt=attempt, retry_after=retry_after,
                    ),
                )
                last_error = error
                await self._sleep_before_retry(attempt, retry_after=retry_after)
                continue

            raise error

        assert last_error is not None
        raise last_error

    def _build_error(self, response: httpx.Response, endpoint: str) -> AnthropicAPIError:
        try:
            body = response.json()
        except ValueError:
            body = None

        error_obj = (body or {}).get("error") if isinstance(body, dict) else None
        error_type = error_obj.get("type") if isinstance(error_obj, dict) else None
        message = (
            error_obj.get("message")
            if isinstance(error_obj, dict) and error_obj.get("message")
            else f"Anthropic Admin API returned HTTP {response.status_code} for {endpoint}"
        )
        request_id = response.headers.get("request-id") or response.headers.get("x-request-id")

        kwargs = dict(
            status_code=response.status_code, endpoint=endpoint,
            error_type=error_type, request_id=request_id, raw_body=body,
        )

        status = response.status_code
        if status == 401:
            return AuthenticationError(message, **kwargs)
        if status == 403:
            return PermissionDeniedError(message, **kwargs)
        if status == 404:
            return NotFoundError(message, **kwargs)
        if status in (400, 409, 422):
            return InvalidRequestError(message, **kwargs)
        if status == 429:
            return RateLimitError(message, retry_after_seconds=self._parse_retry_after(response), **kwargs)
        if status >= 500:
            return ServerError(message, **kwargs)
        return AnthropicAPIError(message, **kwargs)

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> Optional[float]:
        raw = response.headers.get("retry-after")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    async def _sleep_before_retry(self, attempt: int, *, retry_after: Optional[float]) -> None:
        if retry_after is not None:
            delay = retry_after
        else:
            base = self._config.backoff_base_seconds * (2 ** (attempt - 1))
            capped = min(base, self._config.backoff_max_seconds)
            delay = capped * (0.5 + random.random() * 0.5)
        await asyncio.sleep(delay)
