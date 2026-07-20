from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from math import isfinite
from typing import Any

import httpx


MAX_RETRY_DELAY = 5.0


class ProviderError(RuntimeError):
    """A sanitized external-provider failure safe to return to callers."""


class JsonRequester:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        timeout: float = 5.0,
        retries: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.client = client
        self.timeout = timeout
        self.retries = min(2, max(0, retries))
        self.sleep = sleep

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        allow_not_found: bool = False,
        before_attempt: Callable[[int], Awaitable[None]] | None = None,
    ) -> dict[str, Any] | None:
        for attempt in range(self.retries + 1):
            if before_attempt is not None:
                await before_attempt(attempt)
            try:
                response = await self.client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
                if response.status_code == 404 and allow_not_found:
                    return None
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.retries:
                        await self.sleep(_retry_delay(response, attempt))
                        continue
                    raise ProviderError("provider unavailable")
                if response.is_error:
                    raise ProviderError("provider request failed")
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ProviderError("provider returned an invalid response")
                return payload
            except httpx.TimeoutException:
                if attempt < self.retries:
                    await self.sleep(_backoff(attempt))
                    continue
                raise ProviderError("provider request timed out") from None
            except httpx.TransportError:
                if attempt < self.retries:
                    await self.sleep(_backoff(attempt))
                    continue
                raise ProviderError("provider unavailable") from None
            except (ValueError, TypeError):
                raise ProviderError("provider returned an invalid response") from None
        raise ProviderError("provider unavailable")


def _backoff(attempt: int) -> float:
    return 0.25 * (2**attempt)


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    try:
        delay = float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return _backoff(attempt)
    if not isfinite(delay) or delay <= 0:
        return _backoff(attempt)
    return min(delay, MAX_RETRY_DELAY)
