"""Canned Ryanair wire payloads shared across the test suite.

Captured from the live endpoints and trimmed to the smallest shape that
still exercises the parsers. Keep these in sync with
``docs/internal-api-spec.md`` when an endpoint changes shape.
"""

from __future__ import annotations

BASE_URL = "https://services-api.ryanair.com/farfnd/v4"
SCHEDULES_URL = "https://services-api.ryanair.com/timtbl/3/schedules"
AGGREGATE_URL = "https://www.ryanair.com/api/views/locate/3/aggregate/all/en"
ONE_WAY_FARES_URL = f"{BASE_URL}/oneWayFares"


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


def one_way_fare(
    arrival_iata: str = "BCN",
    arrival_name: str = "Barcelona",
    country_code: str = "es",
    price: float = 82.31,
    flight_number: str = "FR6395",
) -> dict:
    """A ``fares[].outbound`` entry with the bits tests vary swapped out."""
    fare = {
        **ONE_WAY_FARE_OUTBOUND,
        "arrivalAirport": {
            **ONE_WAY_FARE_OUTBOUND["arrivalAirport"],
            "iataCode": arrival_iata,
            "name": arrival_name,
            "city": {
                **ONE_WAY_FARE_OUTBOUND["arrivalAirport"]["city"],
                "countryCode": country_code,
            },
        },
        "price": {**ONE_WAY_FARE_OUTBOUND["price"], "value": price},
        "flightNumber": flight_number,
    }
    return fare


ONE_WAY_FARES_PAGE = {"fares": [{"outbound": ONE_WAY_FARE_OUTBOUND}]}


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


def cheapest_per_day_url(origin: str = "DUB", destination: str = "BCN") -> str:
    return f"{BASE_URL}/oneWayFares/{origin}/{destination}/cheapestPerDay"


CHEAPEST_PER_DAY_RESPONSE = {
    "outbound": {
        "fares": [
            {
                "day": "2026-07-01",
                "arrivalDate": "2026-07-01T23:05:00",
                "departureDate": "2026-07-01T19:35:00",
                "price": {
                    "value": 45.99,
                    "valueMainUnit": "45",
                    "valueFractionalUnit": "99",
                    "currencyCode": "EUR",
                    "currencySymbol": "€",
                },
                "soldOut": False,
                "unavailable": False,
            },
            {
                "day": "2026-07-02",
                "arrivalDate": None,
                "departureDate": None,
                "price": None,
                "soldOut": True,
                "unavailable": False,
            },
            {
                "day": "2026-07-03",
                "arrivalDate": "2026-07-04T01:20:00",
                "departureDate": "2026-07-03T21:50:00",
                "price": {
                    "value": 61.50,
                    "valueMainUnit": "61",
                    "valueFractionalUnit": "50",
                    "currencyCode": "EUR",
                    "currencySymbol": "€",
                },
                "soldOut": False,
                "unavailable": False,
            },
        ]
    }
}
