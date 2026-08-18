"""Explore-mode tests using a fake Transport. No network access."""

from flyan.ryanair import RyanAir
from tests.fakes import FakeTransport
from tests.fixtures import AGGREGATE_URL, NETWORK_RESPONSE


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
