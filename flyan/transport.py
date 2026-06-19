"""
HTTP transport seam for the Ryanair API.

The transport owns: the httpx client, the retry policy, the User-Agent
rotation, the cookie warm-up against ryanair.com, the Accept-Encoding
negotiation, and ``nextPage`` pagination across fare-search responses. The
rest of the SDK (``RyanAir`` / ``AsyncRyanAir`` and ``flyan.wire``) talks to
the transport in terms of "give me parsed JSON for this path" — nothing else.

Two adapters ship: ``RyanairTransport`` (sync) and ``AsyncRyanairTransport``
(async). ``CachingTransport`` wraps either with a TTL cache for endpoints
that change rarely (notably ``aggregate``).
"""

from __future__ import annotations

import contextlib
import logging
import random
import time
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    Optional,
    Protocol,
    Tuple,
)

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


_USER_AGENTS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
)

HOMEPAGE_URL = "https://www.ryanair.com"
MAX_PAGES = 20


def _default_headers() -> Dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": random.choice(_USER_AGENTS),
    }


def _is_transient(exc: BaseException) -> bool:
    """Retry only on network issues or 429/5xx; never on programming bugs."""
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return False


def _process_next_page(
    original: Dict[str, Any], next_page: Any
) -> Optional[Dict[str, Any]]:
    """Compute the next page's params, or None if pagination is done."""
    if not next_page:
        return None
    if isinstance(next_page, dict):
        return {**original, **next_page}
    if isinstance(next_page, int):
        return {**original, "offset": next_page}
    return None


class Transport(Protocol):
    """Sync transport interface."""

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch and parse JSON from ``url``."""

    def iter_fare_pages(
        self, url: str, params: Dict[str, Any]
    ) -> Iterator[Dict[str, Any]]:
        """Yield each page of a paginated fare-search response."""

    def close(self) -> None:
        """Release any underlying resources (HTTP client, etc.)."""


class AsyncTransport(Protocol):
    """Async transport interface."""

    async def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch and parse JSON from ``url``."""

    def iter_fare_pages(
        self, url: str, params: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Yield each page of a paginated fare-search response."""

    async def aclose(self) -> None:
        """Release any underlying resources (HTTP client, etc.)."""


class RyanairTransport:
    """Live sync HTTP transport against Ryanair's services-api host."""

    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        warm_session: bool = True,
    ):
        self.client = client or httpx.Client(
            headers=_default_headers(),
            follow_redirects=True,
            timeout=30.0,
        )
        if warm_session:
            try:
                self._get(HOMEPAGE_URL)
            except httpx.HTTPError:
                logger.warning("Could not warm cookies from %s", HOMEPAGE_URL)

    def close(self) -> None:
        # Best-effort cleanup: a double-close or already-broken client
        # shouldn't bubble out of __exit__/finally callers.
        with contextlib.suppress(Exception):
            self.client.close()

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
        next_params: Optional[Dict[str, Any]] = dict(params)
        for _ in range(MAX_PAGES):
            if next_params is None:
                return
            data = self.get_json(url, next_params)
            yield data
            next_params = _process_next_page(params, data.get("nextPage"))


class AsyncRyanairTransport:
    """Live async HTTP transport against Ryanair's services-api host."""

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.client = client or httpx.AsyncClient(
            headers=_default_headers(),
            follow_redirects=True,
            timeout=30.0,
        )
        self._warmed = False

    async def aclose(self) -> None:
        # Best-effort cleanup: a double-close or already-broken client
        # shouldn't bubble out of __aexit__/finally callers.
        with contextlib.suppress(Exception):
            await self.client.aclose()

    async def __aenter__(self) -> "AsyncRyanairTransport":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def _warm(self) -> None:
        if self._warmed:
            return
        self._warmed = True
        try:
            await self._get(HOMEPAGE_URL)
        except httpx.HTTPError:
            logger.warning("Could not warm cookies from %s", HOMEPAGE_URL)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(),
        retry=retry_if_exception(_is_transient),
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        response = await self.client.get(url, params=params or {})
        response.raise_for_status()
        return response

    async def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        await self._warm()
        try:
            response = await self._get(url, params)
        except httpx.HTTPError as exc:
            raise RyanairException(f"request to {url} failed: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise RyanairException(f"non-JSON response from {url}: {exc}") from exc

    async def iter_fare_pages(
        self, url: str, params: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        next_params: Optional[Dict[str, Any]] = dict(params)
        for _ in range(MAX_PAGES):
            if next_params is None:
                return
            data = await self.get_json(url, next_params)
            yield data
            next_params = _process_next_page(params, data.get("nextPage"))


class CachingTransport:
    """TTL-cache wrapper over any sync :class:`Transport`.

    Caches ``get_json`` results keyed by (url, frozen-params). Paginated fare
    searches are never cached — they're price-sensitive and short-lived. Use
    this for the aggregate endpoint and other rarely-changing reads.

    :param inner: the transport to wrap.
    :param ttl: cache lifetime in seconds. Default 1h.
    :param max_entries: drop oldest entries beyond this; keeps memory bounded.
    """

    def __init__(
        self,
        inner: Transport,
        ttl: float = 3600.0,
        max_entries: int = 256,
    ):
        self.inner = inner
        self.ttl = ttl
        self.max_entries = max_entries
        self._store: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Tuple[float, Dict[str, Any]]] = {}

    @staticmethod
    def _key(url: str, params: Optional[Dict[str, Any]]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
        items = tuple(sorted((str(k), str(v)) for k, v in (params or {}).items()))
        return (url, items)

    def _evict(self) -> None:
        if len(self._store) <= self.max_entries:
            return
        # Oldest-first eviction
        for key, _ in sorted(self._store.items(), key=lambda kv: kv[1][0])[
            : len(self._store) - self.max_entries
        ]:
            self._store.pop(key, None)

    def invalidate(self) -> None:
        """Drop every cached entry."""
        self._store.clear()

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        key = self._key(url, params)
        now = time.monotonic()
        cached = self._store.get(key)
        if cached is not None and (now - cached[0]) < self.ttl:
            return cached[1]
        data = self.inner.get_json(url, params)
        self._store[key] = (now, data)
        self._evict()
        return data

    def iter_fare_pages(
        self, url: str, params: Dict[str, Any]
    ) -> Iterator[Dict[str, Any]]:
        # Fare prices change minute-to-minute — caching them is a foot-gun.
        return self.inner.iter_fare_pages(url, params)

    def close(self) -> None:
        self.inner.close()
