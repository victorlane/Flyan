"""Explore-mode tests using a fake Transport. No network access."""

from typing import Any, Iterator

from flyan.ryanair import RyanAir
from flyan.transport import Transport


class FakeTransport(Transport):
    """In-memory transport that returns canned JSON for any URL."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get_json(
        self, url: str, params: dict[str, Any] | None = None
    ) -> Any:
        self.calls.append((url, params))
        return self.responses[url]

    def iter_fare_pages(
        self, url: str, params: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        self.calls.append((url, params))
        yield self.responses[url]

    def close(self) -> None:
        pass


NETWORK_RESPONSE = {
    "airports": [
        {
            "iataCode": "DUB",
            "name": "Dublin",
            "seoName": "dublin",
            "countryCode": "ie",
            "cityCode": "DUBLIN",
            "regionCode": "LEINSTER",
            "currencyCode": "EUR",
            "timeZone": "Europe/Dublin",
            "base": True,
            "coordinates": {"latitude": 53.4213, "longitude": -6.27007},
            "routes": ["airport:BCN", "airport:EDI", "airport:STN"],
            "seasonalRoutes": ["airport:TLV"],
            "categories": [],
            "aliases": [],
        },
        {
            "iataCode": "BCN",
            "name": "Barcelona",
            "seoName": "barcelona",
            "countryCode": "es",
            "cityCode": "BARCELONA",
            "regionCode": "CATALONIA",
            "currencyCode": "EUR",
            "timeZone": "Europe/Madrid",
            "base": False,
            "coordinates": {"latitude": 41.297, "longitude": 2.078},
            "routes": [],
            "seasonalRoutes": [],
            "categories": [],
            "aliases": [],
        },
        {
            "iataCode": "EDI",
            "name": "Edinburgh",
            "seoName": "edinburgh",
            "countryCode": "gb",
            "cityCode": "EDINBURGH",
            "regionCode": "SCOTLAND",
            "currencyCode": "GBP",
            "timeZone": "Europe/London",
            "base": False,
            "coordinates": {"latitude": 55.95, "longitude": -3.37},
            "routes": [],
            "seasonalRoutes": [],
            "categories": [],
            "aliases": [],
        },
        {
            "iataCode": "STN",
            "name": "London Stansted",
            "seoName": "london-stansted",
            "countryCode": "gb",
            "cityCode": "LONDON",
            "regionCode": None,
            "currencyCode": "GBP",
            "timeZone": "Europe/London",
            "base": True,
            "coordinates": {"latitude": 51.88, "longitude": 0.235},
            "routes": [],
            "seasonalRoutes": [],
            "categories": [],
            "aliases": [],
        },
        {
            "iataCode": "TLV",
            "name": "Tel Aviv",
            "seoName": "tel-aviv",
            "countryCode": "il",
            "cityCode": "TELAVIV",
            "regionCode": None,
            "currencyCode": "ILS",
            "timeZone": "Asia/Jerusalem",
            "base": False,
            "coordinates": {"latitude": 32.01, "longitude": 34.89},
            "routes": [],
            "seasonalRoutes": [],
            "categories": [],
            "aliases": [],
        },
    ],
    "countries": [],
    "cities": [],
    "regions": [],
}


AGGREGATE_URL = "https://www.ryanair.com/api/views/locate/3/aggregate/all/en"


def _client() -> RyanAir:
    transport = FakeTransport({AGGREGATE_URL: NETWORK_RESPONSE})
    return RyanAir(transport=transport)


def test_get_destinations_returns_only_reachable_airports() -> None:
    destinations = _client().get_destinations("DUB")
    codes = {a.iata_code for a in destinations}
    assert codes == {"BCN", "EDI", "STN"}


def test_get_destinations_in_country_filters_by_lowercase_iso2() -> None:
    in_gb = _client().get_destinations_in_country("DUB", "gb")
    assert {a.iata_code for a in in_gb} == {"EDI", "STN"}


def test_get_destinations_in_region_filters_by_uppercase_code() -> None:
    in_scotland = _client().get_destinations_in_region("DUB", "SCOTLAND")
    assert [a.iata_code for a in in_scotland] == ["EDI"]


def test_get_destinations_in_city_groups_multi_airport_cities() -> None:
    in_london = _client().get_destinations_in_city("DUB", "LONDON")
    assert [a.iata_code for a in in_london] == ["STN"]


def test_get_seasonal_destinations_uses_seasonal_route_list() -> None:
    seasonal = _client().get_seasonal_destinations("DUB")
    assert [a.iata_code for a in seasonal] == ["TLV"]


def test_explore_by_country_groups_destinations() -> None:
    grouped = _client().explore_by_country("DUB")
    assert set(grouped.keys()) == {"es", "gb"}
    assert {a.iata_code for a in grouped["gb"]} == {"EDI", "STN"}


def test_explore_by_region_collects_missing_region_under_empty_key() -> None:
    grouped = _client().explore_by_region("DUB")
    assert {a.iata_code for a in grouped[""]} == {"STN"}
    assert grouped["SCOTLAND"][0].iata_code == "EDI"
    assert grouped["CATALONIA"][0].iata_code == "BCN"


def test_unknown_origin_returns_empty_list() -> None:
    assert _client().get_destinations("XXX") == []
