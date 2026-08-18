"""Transport tests: retries, UA rotation, warm-up, pagination, caching.

Every HTTP call is answered by an ``httpx.MockTransport`` handler, so the
suite never leaves the process.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import Mock

import httpx
import pytest

from flyan.transport import (
    _USER_AGENTS,
    HOMEPAGE_URL,
    MAX_PAGES,
    CachingTransport,
    RyanairException,
    RyanairTransport,
    _default_headers,
    _is_transient,
    _process_next_page,
)
from tests.fakes import CountingTransport

FARES_URL = "https://services-api.ryanair.com/farfnd/v4/oneWayFares"


def test_import_transport_makes_no_http_requests(monkeypatch):
    """flyan.transport import must not trigger network calls."""
    mock_client = Mock()
    mock_async_client = Mock()
    monkeypatch.setattr("httpx.Client", mock_client)
    monkeypatch.setattr("httpx.AsyncClient", mock_async_client)

    sys.modules.pop("flyan.transport", None)

    import flyan.transport  # noqa: F401  -- imported for its import-time side effects

    mock_client.assert_not_called()
    mock_async_client.assert_not_called()


def test_default_headers_rotate_through_the_known_user_agents():
    seen = {_default_headers()["User-Agent"] for _ in range(200)}
    assert seen
    assert seen <= set(_USER_AGENTS)
    assert len(seen) > 1


def test_default_headers_do_not_advertise_brotli():
    """httpx only decodes br when the brotli extra is installed; don't ask for it."""
    assert _default_headers()["Accept-Encoding"] == "gzip, deflate"


def test_default_headers_ask_for_json():
    headers = _default_headers()
    assert headers["Accept"].startswith("application/json")


@pytest.mark.parametrize(
    "exc, expected",
    [
        (httpx.ConnectError("boom"), True),
        (httpx.ReadTimeout("boom"), True),
        (
            httpx.HTTPStatusError(
                "429",
                request=httpx.Request("GET", FARES_URL),
                response=httpx.Response(429),
            ),
            True,
        ),
        (
            httpx.HTTPStatusError(
                "503",
                request=httpx.Request("GET", FARES_URL),
                response=httpx.Response(503),
            ),
            True,
        ),
        (
            httpx.HTTPStatusError(
                "404",
                request=httpx.Request("GET", FARES_URL),
                response=httpx.Response(404),
            ),
            False,
        ),
        (
            httpx.HTTPStatusError(
                "403",
                request=httpx.Request("GET", FARES_URL),
                response=httpx.Response(403),
            ),
            False,
        ),
        (ValueError("a bug in our own code"), False),
    ],
)
def test_is_transient_classification(exc: BaseException, expected: bool):
    assert _is_transient(exc) is expected


def test_get_json_retries_transient_failures_then_succeeds(mock_client, fast_retries):
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"fares": []})

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    assert transport.get_json(FARES_URL) == {"fares": []}
    assert len(attempts) == 3


def test_get_json_gives_up_after_five_attempts(mock_client, fast_retries):
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(503)

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    with pytest.raises(RyanairException):
        transport.get_json(FARES_URL)
    assert len(attempts) == 5


def test_get_json_does_not_retry_client_errors(mock_client, fast_retries):
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(404)

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    with pytest.raises(RyanairException):
        transport.get_json(FARES_URL)
    assert len(attempts) == 1


def test_get_json_wraps_transport_errors_in_ryanair_exception(mock_client, fast_retries):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    with pytest.raises(RyanairException) as excinfo:
        transport.get_json(FARES_URL)
    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)


def test_get_json_wraps_non_json_bodies(mock_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Access denied</html>")

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    with pytest.raises(RyanairException, match="non-JSON"):
        transport.get_json(FARES_URL)


def test_get_json_forwards_params(mock_client, recorder):
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.record(request)
        return httpx.Response(200, json={})

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    transport.get_json(FARES_URL, {"currency": "GBP"})
    assert recorder.param(0, "currency") == "GBP"


def test_warm_session_hits_the_homepage_first(mock_client, recorder):
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.record(request)
        return httpx.Response(200, json={})

    RyanairTransport(client=mock_client(handler), warm_session=True)
    assert recorder.urls == [HOMEPAGE_URL]


def test_warm_session_can_be_skipped(mock_client, recorder):
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.record(request)
        return httpx.Response(200, json={})

    RyanairTransport(client=mock_client(handler), warm_session=False)
    assert recorder.urls == []


def test_failed_warm_up_does_not_break_construction(mock_client, fast_retries):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ryanair.com unreachable")

    transport = RyanairTransport(client=mock_client(handler), warm_session=True)
    assert transport.client is not None


def test_close_swallows_client_errors():
    class ExplodingClient:
        def close(self) -> None:
            raise RuntimeError("already closed")

    transport = RyanairTransport(client=ExplodingClient(), warm_session=False)
    transport.close()


@pytest.mark.parametrize(
    "next_page, expected",
    [
        (None, None),
        (0, None),
        ({}, None),
        ("2", None),
        (20, {"base": "1", "offset": 20}),
        ({"offset": 20}, {"base": "1", "offset": 20}),
        ({"base": "2"}, {"base": "2"}),
    ],
)
def test_process_next_page(next_page: Any, expected: Any):
    assert _process_next_page({"base": "1"}, next_page) == expected


def test_iter_fare_pages_follows_integer_next_page_as_offset(mock_client, recorder):
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.record(request)
        offset = int(request.url.params.get("offset", 0))
        if offset == 0:
            return httpx.Response(200, json={"fares": ["a"], "nextPage": 20})
        if offset == 20:
            return httpx.Response(200, json={"fares": ["b"], "nextPage": 40})
        return httpx.Response(200, json={"fares": ["c"]})

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    pages = list(transport.iter_fare_pages(FARES_URL, {"departureAirportIataCode": "DUB"}))

    assert [p["fares"] for p in pages] == [["a"], ["b"], ["c"]]
    assert [recorder.param(i, "offset") for i in range(3)] == [None, "20", "40"]


def test_iter_fare_pages_keeps_the_original_params_on_every_page(mock_client, recorder):
    """Offsets replace, they don't accumulate: page 3 must still carry the search."""

    def handler(request: httpx.Request) -> httpx.Response:
        recorder.record(request)
        offset = int(request.url.params.get("offset", 0))
        if offset < 40:
            return httpx.Response(200, json={"fares": [], "nextPage": offset + 20})
        return httpx.Response(200, json={"fares": []})

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    list(transport.iter_fare_pages(FARES_URL, {"departureAirportIataCode": "DUB"}))

    assert all(p["departureAirportIataCode"] == "DUB" for p in recorder.params)


def test_iter_fare_pages_merges_dict_next_page(mock_client, recorder):
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.record(request)
        if "page" not in request.url.params:
            return httpx.Response(200, json={"fares": [], "nextPage": {"page": 2}})
        return httpx.Response(200, json={"fares": []})

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    pages = list(transport.iter_fare_pages(FARES_URL, {"departureAirportIataCode": "DUB"}))

    assert len(pages) == 2
    assert recorder.param(1, "page") == "2"


def test_iter_fare_pages_stops_when_next_page_is_absent(mock_client):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"fares": []})

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    pages = list(transport.iter_fare_pages(FARES_URL, {}))

    assert len(pages) == 1
    assert len(calls) == 1


def test_iter_fare_pages_is_capped_at_max_pages(mock_client):
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("offset", 0))
        return httpx.Response(200, json={"fares": [], "nextPage": offset + 20})

    transport = RyanairTransport(client=mock_client(handler), warm_session=False)
    pages = list(transport.iter_fare_pages(FARES_URL, {}))

    assert len(pages) == MAX_PAGES


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    """A hand-cranked replacement for ``time.monotonic`` inside the transport."""
    import flyan.transport as transport_module

    now = {"t": 1000.0}
    monkeypatch.setattr(transport_module.time, "monotonic", lambda: now["t"])

    def advance(seconds: float) -> None:
        now["t"] += seconds

    return advance


def test_caching_transport_serves_repeat_reads_from_cache(clock):
    inner = CountingTransport()
    cache = CachingTransport(inner, ttl=60.0)

    assert cache.get_json("u", {"a": 1}) == {"n": 1}
    assert cache.get_json("u", {"a": 1}) == {"n": 1}
    assert len(inner.calls) == 1


def test_caching_transport_refetches_after_the_ttl_expires(clock):
    inner = CountingTransport()
    cache = CachingTransport(inner, ttl=60.0)

    cache.get_json("u")
    clock(59.0)
    assert cache.get_json("u") == {"n": 1}
    clock(2.0)
    assert cache.get_json("u") == {"n": 2}
    assert len(inner.calls) == 2


def test_caching_transport_key_ignores_param_order_and_type(clock):
    inner = CountingTransport()
    cache = CachingTransport(inner, ttl=60.0)

    cache.get_json("u", {"a": 1, "b": "2"})
    cache.get_json("u", {"b": 2, "a": "1"})
    assert len(inner.calls) == 1


def test_caching_transport_separates_different_params(clock):
    inner = CountingTransport()
    cache = CachingTransport(inner, ttl=60.0)

    assert cache.get_json("u", {"a": 1}) == {"n": 1}
    assert cache.get_json("u", {"a": 2}) == {"n": 2}
    assert cache.get_json("v", {"a": 1}) == {"n": 3}
    assert len(inner.calls) == 3


def test_caching_transport_invalidate_drops_everything(clock):
    inner = CountingTransport()
    cache = CachingTransport(inner, ttl=60.0)

    cache.get_json("u")
    cache.invalidate()
    assert cache.get_json("u") == {"n": 2}


def test_caching_transport_evicts_oldest_entries_beyond_max(clock):
    inner = CountingTransport()
    cache = CachingTransport(inner, ttl=600.0, max_entries=2)

    cache.get_json("oldest")
    clock(1.0)
    cache.get_json("middle")
    clock(1.0)
    cache.get_json("newest")

    cache.get_json("middle")
    cache.get_json("newest")
    assert len(inner.calls) == 3

    cache.get_json("oldest")
    assert len(inner.calls) == 4


def test_caching_transport_never_caches_fare_pages(clock):
    inner = CountingTransport()
    cache = CachingTransport(inner, ttl=600.0)

    assert [p for p in cache.iter_fare_pages("u", {})] == [{"n": 1}]
    assert [p for p in cache.iter_fare_pages("u", {})] == [{"n": 2}]


def test_caching_transport_close_delegates_to_inner():
    inner = CountingTransport()
    CachingTransport(inner).close()
    assert inner.closed is True
