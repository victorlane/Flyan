"""Fixture-based tests for the wire layer. No network access."""

from datetime import datetime

from flyan.misc import (
    FlightSearchParams,
    NetworkAirport,
    ReturnFlightSearchParams,
)
from flyan.wire import (
    parse_flight,
    parse_network,
    parse_network_airport,
    serialize_search_params,
)

ONE_WAY_FARE_OUTBOUND = {
    "departureAirport": {
        "countryName": "Ireland",
        "iataCode": "DUB",
        "name": "Dublin",
        "seoName": "dublin",
        "city": {
            "name": "Dublin",
            "code": "DUBLIN",
            "countryCode": "ie",
            "macCode": None,
        },
    },
    "arrivalAirport": {
        "countryName": "Spain",
        "iataCode": "BCN",
        "name": "Barcelona",
        "seoName": "barcelona",
        "city": {
            "name": "Barcelona",
            "code": "BARCELONA",
            "countryCode": "es",
            "macCode": None,
        },
    },
    "departureDate": "2026-07-02T21:50:00",
    "arrivalDate": "2026-07-03T01:20:00",
    "price": {
        "value": 82.31,
        "valueMainUnit": "82",
        "valueFractionalUnit": "31",
        "currencyCode": "EUR",
        "currencySymbol": "€",
    },
    "flightKey": "FR~6395~ ~~DUB~07/02/2026 21:50~BCN~07/03/2026 01:20~ ~ ",
    "flightNumber": "FR6395",
    "previousPrice": None,
    "priceUpdated": 1749594000000,
}


NETWORK_AIRPORT_DUB = {
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
    "routes": [
        "airport:BCN",
        "city:LONDON",
        "country:es",
        "region:SCOTLAND",
    ],
    "seasonalRoutes": ["airport:TLV"],
    "categories": ["BEACH"],
    "aliases": [],
    "priority": 1,
}


def test_parse_flight_translates_field_names_and_iso_dates() -> None:
    flight = parse_flight(ONE_WAY_FARE_OUTBOUND)
    assert flight.flight_number == "FR6395"
    assert flight.departure_airport.iata_code == "DUB"
    assert flight.arrival_airport.iata_code == "BCN"
    assert flight.departure_date == datetime.fromisoformat("2026-07-02T21:50:00")
    assert flight.price == 82.31
    assert flight.currency == "EUR"
    assert flight.previous_price is None
    assert flight.price_updated is not None


def test_serialize_search_params_lowercases_country_code() -> None:
    """Country codes must hit the wire lowercase; uppercase silently returns 0 fares."""
    params = FlightSearchParams(
        from_airport="DUB",
        from_date=datetime(2099, 1, 1),
        to_date=datetime(2099, 1, 7),
        destination_country="ES",
    )
    wire = serialize_search_params(params)
    assert wire["arrivalCountryCode"] == "es"


def test_serialize_search_params_includes_currency_when_provided() -> None:
    params = FlightSearchParams(
        from_airport="DUB",
        from_date=datetime(2099, 1, 1),
        to_date=datetime(2099, 1, 7),
    )
    wire = serialize_search_params(params, currency="USD")
    assert wire["currency"] == "USD"


def test_serialize_search_params_omits_currency_when_not_provided() -> None:
    params = FlightSearchParams(
        from_airport="DUB",
        from_date=datetime(2099, 1, 1),
        to_date=datetime(2099, 1, 7),
    )
    wire = serialize_search_params(params)
    assert "currency" not in wire


def test_serialize_return_search_params_adds_inbound_window() -> None:
    params = ReturnFlightSearchParams(
        from_airport="DUB",
        from_date=datetime(2099, 1, 1),
        to_date=datetime(2099, 1, 7),
        return_date_from=datetime(2099, 1, 10),
        return_date_to=datetime(2099, 1, 14),
    )
    wire = serialize_search_params(params)
    assert wire["inboundDepartureDateFrom"] == "2099-01-10"
    assert wire["inboundDepartureDateTo"] == "2099-01-14"


def test_parse_network_airport_exposes_typed_route_accessors() -> None:
    airport = parse_network_airport(NETWORK_AIRPORT_DUB)
    assert isinstance(airport, NetworkAirport)
    assert airport.iata_code == "DUB"
    assert airport.airport_routes() == ["BCN"]
    assert airport.country_routes() == ["es"]
    assert airport.seasonal_airport_routes() == ["TLV"]


def test_parse_network_returns_all_top_level_groups() -> None:
    network = parse_network(
        {
            "airports": [NETWORK_AIRPORT_DUB],
            "countries": [
                {
                    "code": "ie",
                    "iso3code": "irl",
                    "name": "Ireland",
                    "currency": "EUR",
                    "defaultAirportCode": "DUB",
                    "schengen": False,
                }
            ],
            "cities": [{"name": "Dublin", "code": "DUBLIN", "countryCode": "ie"}],
            "regions": [
                {
                    "name": "Leinster",
                    "code": "LEINSTER",
                    "cites": [],
                }
            ],
        }
    )
    assert len(network.airports) == 1
    assert network.countries[0].code == "ie"
    assert network.cities[0]["code"] == "DUBLIN"
    assert network.regions[0]["code"] == "LEINSTER"
