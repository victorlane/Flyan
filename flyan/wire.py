"""
Translation between Flyan's public models and Ryanair's wire format.

The Ryanair API field names (``departureAirportIataCode`` etc.) and quirks
(lowercase iso2 country codes, currency-as-query-param) live here and nowhere
else. ``flyan.misc`` describes what callers care about; this module describes
what the API expects.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from .misc import (
    Airport,
    DailyFare,
    Flight,
    FlightSearchParams,
    Network,
    NetworkAirport,
    NetworkCountry,
    ReturnFlight,
    ReturnFlightSearchParams,
    TimetableFlight,
)


# --- serialize ----------------------------------------------------------------


def serialize_search_params(
    params: FlightSearchParams, currency: Optional[str] = None
) -> Dict[str, Any]:
    """Render a search-params model into Ryanair's query-string dict."""
    out: Dict[str, Any] = {
        "departureAirportIataCode": params.from_airport,
        "outboundDepartureDateFrom": params.from_date.date().isoformat(),
        "outboundDepartureDateTo": params.to_date.date().isoformat(),
        "outboundDepartureTimeFrom": params.departure_time_from or "00:00",
        "outboundDepartureTimeTo": params.departure_time_to or "23:59",
    }
    if params.destination_country:
        # API requires lowercase iso2; uppercase silently returns no fares.
        out["arrivalCountryCode"] = params.destination_country.lower()
    if params.max_price:
        out["priceValueTo"] = params.max_price
    if params.to_airport:
        out["arrivalAirportIataCode"] = params.to_airport
    if currency:
        out["currency"] = currency

    if isinstance(params, ReturnFlightSearchParams):
        out["inboundDepartureDateFrom"] = params.return_date_from.date().isoformat()
        out["inboundDepartureDateTo"] = params.return_date_to.date().isoformat()
        if params.inbound_departure_time_from:
            out["inboundDepartureTimeFrom"] = params.inbound_departure_time_from
        if params.inbound_departure_time_to:
            out["inboundDepartureTimeTo"] = params.inbound_departure_time_to

    return out


# --- parse --------------------------------------------------------------------


def parse_airport(raw: Dict[str, Any]) -> Airport:
    return Airport(
        country_name=raw["countryName"],
        iata_code=raw["iataCode"],
        name=raw["name"],
        seo_name=raw["seoName"],
        city_name=raw["city"]["name"],
        city_code=raw["city"]["code"],
        city_country_code=raw["city"]["countryCode"],
    )


def parse_flight(raw: Dict[str, Any]) -> Flight:
    """Parse a single leg (outbound or inbound) from a fares response."""
    price_updated_ms = raw.get("priceUpdated")
    price_updated = (
        datetime.fromtimestamp(price_updated_ms / 1000)
        if isinstance(price_updated_ms, (int, float))
        else None
    )
    return Flight(
        departure_airport=parse_airport(raw["departureAirport"]),
        arrival_airport=parse_airport(raw["arrivalAirport"]),
        departure_date=datetime.fromisoformat(raw["departureDate"]),
        arrival_date=datetime.fromisoformat(raw["arrivalDate"]),
        price=raw["price"]["value"],
        currency=raw["price"]["currencyCode"],
        flight_key=raw["flightKey"],
        flight_number=raw["flightNumber"],
        previous_price=raw.get("previousPrice"),
        price_updated=price_updated,
    )


def parse_return_flight(raw: Dict[str, Any]) -> ReturnFlight:
    return ReturnFlight(
        outbound=parse_flight(raw["outbound"]),
        inbound=parse_flight(raw["inbound"]),
        summary_price=raw["summary"]["price"]["value"],
        summary_currency=raw["summary"]["price"]["currencyCode"],
        previous_price=raw["summary"].get("previousPrice") or 0,
    )


def parse_daily_fare(raw: Dict[str, Any]) -> DailyFare:
    price = raw.get("price") or {}
    return DailyFare(
        day=datetime.fromisoformat(raw["day"]),
        departure_date=(
            datetime.fromisoformat(raw["departureDate"])
            if raw.get("departureDate")
            else None
        ),
        arrival_date=(
            datetime.fromisoformat(raw["arrivalDate"])
            if raw.get("arrivalDate")
            else None
        ),
        price=price.get("value"),
        currency=price.get("currencyCode"),
        sold_out=bool(raw.get("soldOut")),
        unavailable=bool(raw.get("unavailable")),
    )


def parse_timetable_flight(raw: Dict[str, Any]) -> TimetableFlight:
    return TimetableFlight(
        carrier_code=raw["carrierCode"],
        flight_number=raw["number"],
        departure_time=raw["departureTime"],
        arrival_time=raw["arrivalTime"],
    )


def parse_network_airport(raw: Dict[str, Any]) -> NetworkAirport:
    return NetworkAirport(
        iata_code=raw["iataCode"],
        name=raw["name"],
        seo_name=raw["seoName"],
        country_code=raw["countryCode"],
        city_code=raw["cityCode"],
        region_code=raw.get("regionCode"),
        currency_code=raw["currencyCode"],
        time_zone=raw["timeZone"],
        base=bool(raw.get("base", False)),
        latitude=raw["coordinates"]["latitude"],
        longitude=raw["coordinates"]["longitude"],
        routes=raw.get("routes", []),
        seasonal_routes=raw.get("seasonalRoutes", []),
        categories=raw.get("categories", []),
        aliases=raw.get("aliases", []),
        priority=raw.get("priority"),
    )


def parse_network_country(raw: Dict[str, Any]) -> NetworkCountry:
    return NetworkCountry(
        code=raw["code"],
        iso3_code=raw["iso3code"],
        name=raw["name"],
        currency=raw["currency"],
        default_airport_code=raw.get("defaultAirportCode"),
        schengen=bool(raw.get("schengen", False)),
    )


def parse_network(raw: Dict[str, Any]) -> Network:
    return Network(
        airports=[parse_network_airport(a) for a in raw.get("airports", [])],
        countries=[parse_network_country(c) for c in raw.get("countries", [])],
        cities=raw.get("cities", []),
        regions=raw.get("regions", []),
    )
