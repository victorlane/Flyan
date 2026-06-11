"""
HTTP transport seam for the Ryanair API.

The transport owns: the httpx client, the retry policy, the User-Agent
rotation, the cookie warm-up against ryanair.com, the Accept-Encoding
negotiation, and ``nextPage`` pagination across fare-search responses. The
rest of the SDK (``RyanAir`` and ``flyan.wire``) talks to the transport in
terms of "give me parsed JSON for this path" — nothing else.

A second adapter (a recorded-fixture transport, or an httpx ``MockTransport``)
satisfies the same interface, which is how the parser and client layers get
tested without hitting the network.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, Iterator, Optional, Protocol

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("Flyan")


class RyanairException(Exception):
    """Raised when the transport cannot satisfy a request."""

    def __init__(self, message: str):
        super().__init__(f"Ryanair API: {message}")


# Bundled UA rotation — avoids fake-useragent's network call on import,
# which breaks air-gapped CI and slows cold start.
_USER_AGENTS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)

HOMEPAGE_URL = "https://www.ryanair.com"
MAX_PAGES = 20


def _is_transient(exc: BaseException) -> bool:
    """Retry only on network issues or 429/5xx; never on programming bugs."""
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return False


class Transport(Protocol):
    """Anything the SDK can use as a Ryanair transport."""

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]: ...

    def iter_fare_pages(
        self, url: str, params: Dict[str, Any]
    ) -> Iterator[Dict[str, Any]]: ...

    def close(self) -> None: ...


class RyanairTransport:
    """Live HTTP transport against Ryanair's services-api host."""

    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        warm_session: bool = True,
    ):
        self.client = client or httpx.Client(
            headers={
                "Accept": "application/json, text/plain, */*",
                # Only advertise encodings httpx can decode without extra deps.
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-GB,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "User-Agent": random.choice(_USER_AGENTS),
            },
            follow_redirects=True,
            timeout=30.0,
        )
        if warm_session:
            # services-api host often 403s cold; warm cookies from the homepage.
            try:
                self._get(HOMEPAGE_URL)
            except httpx.HTTPError:
                logger.warning("Could not warm cookies from %s", HOMEPAGE_URL)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        response = self.client.get(url, params=params or {})
        response.raise_for_status()
        return response

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET ``url`` and return the decoded JSON body.

        Raises ``RyanairException`` for any transport, status, or decode failure.
        """
        try:
            response = self._get(url, params)
        except httpx.HTTPError as exc:
            raise RyanairException(f"request to {url} failed: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise RyanairException(f"non-JSON response from {url}: {exc}") from exc

    def iter_fare_pages(
        self, url: str, params: Dict[str, Any]
    ) -> Iterator[Dict[str, Any]]:
        """Yield one or more fare-search response payloads, following ``nextPage``.

        Each yielded value is the parsed JSON of one page (with its ``fares``
        key). The caller is responsible for flattening across pages. Raises
        ``RyanairException`` on the first page failure; subsequent pages that
        cease to return ``nextPage`` simply end the iteration.
        """
        next_params: Optional[Dict[str, Any]] = dict(params)
        for _ in range(MAX_PAGES):
            if next_params is None:
                return
            data = self.get_json(url, next_params)
            yield data
            next_page = data.get("nextPage")
            if not next_page:
                return
            # nextPage observed as dict (param overrides) or int (offset).
            if isinstance(next_page, dict):
                next_params = {**params, **next_page}
            elif isinstance(next_page, int):
                next_params = {**params, "offset": next_page}
            else:
                return
