"""In-memory transport doubles shared across the test suite.

Anything that talks to a ``Transport`` uses one of these instead of the
real HTTP adapters, so the suite never touches the network.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator


class FakeTransport:
    """Sync transport that returns canned JSON keyed by URL."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.closed = False

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((url, params))
        return self.responses[url]

    def iter_fare_pages(self, url: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        self.calls.append((url, params))
        pages = self.responses[url]
        if isinstance(pages, list):
            yield from pages
        else:
            yield pages

    def close(self) -> None:
        self.closed = True


class FakeAsyncTransport:
    """Async mirror of :class:`FakeTransport`."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.closed = False

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((url, params))
        return self.responses[url]

    async def iter_fare_pages(
        self, url: str, params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append((url, params))
        pages = self.responses[url]
        if isinstance(pages, list):
            for page in pages:
                yield page
        else:
            yield pages

    async def aclose(self) -> None:
        self.closed = True


class CountingTransport:
    """Sync transport whose payload changes on every call.

    Lets a caching test tell a cache hit from a refetch: the same request
    twice returns ``{"n": 1}`` twice only if the second one was cached.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.closed = False

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((url, params))
        return {"n": len(self.calls)}

    def iter_fare_pages(self, url: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        self.calls.append((url, params))
        yield {"n": len(self.calls)}

    def close(self) -> None:
        self.closed = True
