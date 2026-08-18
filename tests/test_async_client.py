"""AsyncRyanAir tests against a fake AsyncTransport. No network access.

Mirrors ``tests/test_explore.py`` so the sync and async clients stay in
lockstep, plus the async-only surface (warm-up, ``aclose``, pagination).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest

from flyan.async_client import AsyncRyanAir
from flyan.misc import FlightSearchParams
from flyan.transport import AsyncRyanairTransport, RyanairException
from tests.fakes import FakeAsyncTransport
from tests.fixtures import (
    AGGREGATE_URL,
    CHEAPEST_PER_DAY_RESPONSE,
    NETWORK_RESPONSE,
    ONE_WAY_FARES_URL,
    cheapest_per_day_url,
    one_way_fare,
)

pytestmark = pytest.mark.asyncio


def _client(responses: dict | None = None) -> AsyncRyanAir:
    transport = FakeAsyncTransport({AGGREGATE_URL: NETWORK_RESPONSE, **(responses or {})})
    return AsyncRyanAir(transport=transport)


def _search_params(**overrides) -> FlightSearchParams:
    tomorrow = datetime.now() + timedelta(days=1)
    defaults = {
        "from_airport": "DUB",
        "from_date": tomorrow,
        "to_date": tomorrow + timedelta(days=7),
    }
    return FlightSearchParams(**{**defaults, **overrides})


async def test_get_destinations_returns_only_reachable_airports() -> None:
    destinations = await _client().get_destinations("DUB")
    assert {a.iata_code for a in destinations} == {"BCN", "EDI", "STN"}


async def test_get_destinations_in_country_filters_by_lowercase_iso2() -> None:
    in_gb = await _client().get_destinations_in_country("DUB", "gb")
    assert {a.iata_code for a in in_gb} == {"EDI", "STN"}


async def test_get_destinations_in_region_filters_by_uppercase_code() -> None:
    in_scotland = await _client().get_destinations_in_region("DUB", "scotland")
    assert [a.iata_code for a in in_scotland] == ["EDI"]


async def test_get_destinations_in_city_groups_multi_airport_cities() -> None:
    in_london = await _client().get_destinations_in_city("DUB", "london")
    assert [a.iata_code for a in in_london] == ["STN"]


async def test_get_seasonal_destinations_uses_seasonal_route_list() -> None:
    seasonal = await _client().get_seasonal_destinations("DUB")
    assert [a.iata_code for a in seasonal] == ["TLV"]


async def test_explore_by_country_groups_destinations() -> None:
    grouped = await _client().explore_by_country("DUB")
    assert set(grouped) == {"es", "gb"}
    assert {a.iata_code for a in grouped["gb"]} == {"EDI", "STN"}


async def test_explore_by_region_collects_missing_region_under_empty_key() -> None:
    grouped = await _client().explore_by_region("DUB")
    assert {a.iata_code for a in grouped[""]} == {"STN"}
    assert grouped["SCOTLAND"][0].iata_code == "EDI"


async def test_unknown_origin_returns_empty_list() -> None:
    assert await _client().get_destinations("XXX") == []


async def test_validate_route_checks_the_network() -> None:
    client = _client()
    assert await client.validate_route("dub", "bcn") is True
    assert await client.validate_route("DUB", "TLV") is False
    assert await client.validate_route("XXX", "BCN") is False


async def test_get_oneways_flattens_every_page() -> None:
    pages = [
        {"fares": [{"outbound": one_way_fare("BCN", price=50.0)}]},
        {"fares": [{"outbound": one_way_fare("EDI", "Edinburgh", "gb", price=30.0)}]},
    ]
    client = _client({ONE_WAY_FARES_URL: pages})

    flights = await client.get_oneways(_search_params())

    assert [f.arrival_airport.iata_code for f in flights] == ["BCN", "EDI"]
    assert [f.price for f in flights] == [50.0, 30.0]


async def test_get_oneways_sends_the_serialized_search_params() -> None:
    client = _client({ONE_WAY_FARES_URL: {"fares": []}})

    await client.get_oneways(_search_params(destination_country="ES", max_price=100))

    url, params = client.transport.calls[0]
    assert url == ONE_WAY_FARES_URL
    assert params["departureAirportIataCode"] == "DUB"
    assert params["arrivalCountryCode"] == "es"
    assert params["priceValueTo"] == 100
    assert params["currency"] == "EUR"


async def test_get_oneways_raises_on_unexpected_shape() -> None:
    client = _client({ONE_WAY_FARES_URL: {"fares": [{"outbound": {"nope": 1}}]}})

    with pytest.raises(RyanairException, match="unexpected one-way fare shape"):
        await client.get_oneways(_search_params())


async def test_get_cheapest_per_day_parses_unpriced_days() -> None:
    client = _client({cheapest_per_day_url(): CHEAPEST_PER_DAY_RESPONSE})

    fares = await client.get_cheapest_per_day("dub", "bcn", datetime(2026, 7, 14))

    assert [f.price for f in fares] == [45.99, None, 61.50]
    assert fares[1].sold_out is True
    _, params = client.transport.calls[0]
    assert params["outboundMonthOfDate"] == "2026-07-01"


async def test_explore_with_fares_joins_cheapest_fare_per_destination() -> None:
    client = _client(
        {
            ONE_WAY_FARES_URL: {
                "fares": [
                    {"outbound": one_way_fare("BCN", price=90.0)},
                    {"outbound": one_way_fare("BCN", price=40.0)},
                ]
            }
        }
    )
    params = _search_params()

    results = await client.explore_with_fares("DUB", params.from_date, params.to_date)

    by_code = {r.airport.iata_code: r for r in results}
    assert by_code["BCN"].fare is not None
    assert by_code["BCN"].fare.price == 40.0
    assert by_code["EDI"].fare is None


async def test_unknown_currency_falls_back_to_eur() -> None:
    assert AsyncRyanAir(currency="XYZ", transport=FakeAsyncTransport({})).currency == "EUR"
    assert AsyncRyanAir(currency="GBP", transport=FakeAsyncTransport({})).currency == "GBP"


async def test_async_context_manager_closes_the_transport() -> None:
    transport = FakeAsyncTransport({AGGREGATE_URL: NETWORK_RESPONSE})
    async with AsyncRyanAir(transport=transport) as client:
        assert await client.get_destinations("DUB")
    assert transport.closed is True


async def test_async_transport_warms_cookies_once(mock_async_client, recorder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.record(request)
        return httpx.Response(200, json={})

    transport = AsyncRyanairTransport(client=mock_async_client(handler))
    await transport.get_json(ONE_WAY_FARES_URL)
    await transport.get_json(ONE_WAY_FARES_URL)
    await transport.aclose()

    assert recorder.urls.count("https://www.ryanair.com") == 1
    assert len(recorder.urls) == 3


async def test_async_transport_retries_transient_failures(mock_async_client, fast_retries) -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"fares": []})

    transport = AsyncRyanairTransport(client=mock_async_client(handler))
    transport._warmed = True

    assert await transport.get_json(ONE_WAY_FARES_URL) == {"fares": []}
    assert len(attempts) == 3
    await transport.aclose()


async def test_async_transport_wraps_failures(mock_async_client, fast_retries) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = AsyncRyanairTransport(client=mock_async_client(handler))
    transport._warmed = True

    with pytest.raises(RyanairException):
        await transport.get_json(ONE_WAY_FARES_URL)
    await transport.aclose()


async def test_async_iter_fare_pages_follows_next_page(mock_async_client, recorder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.record(request)
        offset = int(request.url.params.get("offset", 0))
        if offset == 0:
            return httpx.Response(200, json={"fares": ["a"], "nextPage": 20})
        return httpx.Response(200, json={"fares": ["b"]})

    transport = AsyncRyanairTransport(client=mock_async_client(handler))
    transport._warmed = True

    pages = [p async for p in transport.iter_fare_pages(ONE_WAY_FARES_URL, {"a": "1"})]
    await transport.aclose()

    assert [p["fares"] for p in pages] == [["a"], ["b"]]
    assert recorder.param(1, "offset") == "20"


async def test_async_transport_aclose_swallows_errors() -> None:
    class ExplodingClient:
        async def aclose(self) -> None:
            raise RuntimeError("already closed")

    await AsyncRyanairTransport(client=ExplodingClient()).aclose()
