"""Shared async HTTP plumbing for every Google API call.

Responsibilities:

* one pooled ``httpx.AsyncClient`` per event loop
* bounded concurrency
* retries with exponential backoff + jitter on 429 / 5xx
* mapping HTTP failures onto the provider exception hierarchy
"""

import asyncio
import logging
import random
from typing import Any, Dict, Optional

import httpx

from app.config import settings

from .exceptions import (
    GoogleAPIError,
    GoogleNotFound,
    GoogleRateLimited,
    GoogleUnauthorized,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_clients: "dict[asyncio.AbstractEventLoop, httpx.AsyncClient]" = {}
_semaphores: "dict[asyncio.AbstractEventLoop, asyncio.Semaphore]" = {}


def _get_client() -> httpx.AsyncClient:
    """Return the pooled client bound to the running event loop."""

    loop = asyncio.get_running_loop()
    client = _clients.get(loop)

    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.GOOGLE_TIMEOUT_SECONDS),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
            headers={"User-Agent": "FinMate/1.0"},
        )
        _clients[loop] = client

    return client


def _get_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    semaphore = _semaphores.get(loop)

    if semaphore is None:
        semaphore = asyncio.Semaphore(
            settings.GOOGLE_MAX_CONCURRENT_REQUESTS
        )
        _semaphores[loop] = semaphore

    return semaphore


async def close_http_clients() -> None:
    """Close pooled clients (call on application shutdown)."""

    for loop, client in list(_clients.items()):
        if not client.is_closed:
            await client.aclose()
        _clients.pop(loop, None)

    _semaphores.clear()


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]

    if isinstance(payload, dict):
        error = payload.get("error")

        if isinstance(error, dict):
            return str(error.get("message") or error)

        if error:
            description = payload.get("error_description")
            return f"{error}: {description}" if description else str(error)

    return str(payload)[:200]


async def request_json(
    method: str,
    url: str,
    *,
    access_token: Optional[str] = None,
    params: Optional[Any] = None,
    data: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    expect_json: bool = True,
) -> Any:
    """Perform a Google API request and return the decoded JSON body."""

    headers: Dict[str, str] = {}

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    client = _get_client()
    semaphore = _get_semaphore()
    attempts = max(1, settings.GOOGLE_MAX_RETRIES)
    last_error: Optional[Exception] = None

    for attempt in range(attempts):

        try:
            async with semaphore:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json_body,
                )

        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "Google request failed (%s %s, attempt %s/%s): %s",
                method,
                url,
                attempt + 1,
                attempts,
                exc,
            )
            await _sleep_backoff(attempt)
            continue

        if response.status_code < 300:
            if not expect_json or not response.content:
                return response.text

            try:
                return response.json()
            except ValueError as exc:
                raise GoogleAPIError(
                    response.status_code,
                    "Google returned a malformed JSON body",
                ) from exc

        if response.status_code == 401:
            raise GoogleUnauthorized(_error_message(response))

        if response.status_code == 404:
            raise GoogleNotFound(_error_message(response))

        if response.status_code in RETRYABLE_STATUS:
            last_error = GoogleRateLimited(_error_message(response))
            logger.warning(
                "Google throttled/failed (%s %s -> %s, attempt %s/%s)",
                method,
                url,
                response.status_code,
                attempt + 1,
                attempts,
            )
            await _sleep_backoff(
                attempt,
                retry_after=response.headers.get("Retry-After"),
            )
            continue

        raise GoogleAPIError(
            response.status_code,
            _error_message(response),
        )

    if isinstance(last_error, GoogleRateLimited):
        raise last_error

    raise GoogleAPIError(
        503,
        f"Google is unreachable: {last_error}",
    )


async def _sleep_backoff(
    attempt: int,
    retry_after: Optional[str] = None,
) -> None:

    if retry_after:
        try:
            await asyncio.sleep(min(float(retry_after), 10.0))
            return
        except ValueError:
            pass

    delay = min(2 ** attempt, 8) + random.uniform(0, 0.5)

    await asyncio.sleep(delay)
