"""Shared pytest fixtures. Nothing here touches the network."""

from __future__ import annotations

from typing import Any, Callable, Optional

import httpx
import pytest

from flyan.transport import (
    AsyncRyanairTransport,
    RyanairTransport,
    _default_headers,
)


@pytest.fixture
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip the exponential backoff so retry tests run in microseconds.

    Only the sleep is patched, so attempt counts and the transient/permanent
    classification still go through the real tenacity policy.
    """

    async def _async_no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(RyanairTransport._get.retry, "sleep", lambda _seconds: None)
    monkeypatch.setattr(AsyncRyanairTransport._get.retry, "sleep", _async_no_sleep)


Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def mock_client() -> Callable[[Handler], httpx.Client]:
    """Build an ``httpx.Client`` whose requests are answered by ``handler``."""

    def build(handler: Handler) -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(handler),
            headers=_default_headers(),
            follow_redirects=True,
        )

    return build


@pytest.fixture
def mock_async_client() -> Callable[[Handler], httpx.AsyncClient]:
    """Async mirror of :func:`mock_client`."""

    def build(handler: Handler) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers=_default_headers(),
            follow_redirects=True,
        )

    return build


class Recorder:
    """Collects the requests an ``httpx.MockTransport`` handler saw."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.params: list[dict[str, Any]] = []

    def record(self, request: httpx.Request) -> None:
        self.urls.append(str(request.url).split("?")[0])
        self.params.append(dict(request.url.params))

    def param(self, index: int, name: str) -> Optional[str]:
        return self.params[index].get(name)


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()
