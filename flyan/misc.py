"""
Public data models for Flyan.

These describe what callers care about (a flight, a search, a network). The
Ryanair wire format — field names, query-param quirks — lives in
:mod:`flyan.wire`; nothing in this module knows about it.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from importlib.resources import files
from typing import Any, Dict, Optional

from pydantic import BaseModel, field_validator


def _load_json_file(filename: str) -> Dict[str, Any]:
    """Load JSON file from the package resources, falling back to the filesystem."""
    try:
        package_files = files("flyan")
        json_file = package_files / filename
        if json_file.is_file():
            return json.loads(json_file.read_text(encoding="utf-8"))
    except Exception:
        pass

    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, filename)
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Could not find {filename} in {current_dir}. "
            f"Make sure the JSON files are included in the package."
        ) from exc


currencies: Dict[str, Any] = _load_json_file("currencies.json")


_IATA_PATTERN = re.compile(r"^[A-Z]{3}$")


class Airport(BaseModel):
    country_name: str
    iata_code: str
    name: str
    seo_name: str
    city_name: str
    city_code: str
    city_country_code: str


class Flight(BaseModel):
    departure_airport: Airport
    arrival_airport: Airport
    departure_date: datetime
    arrival_date: datetime
    price: float
    currency: str
    flight_key: str
    flight_number: str
    previous_price: Optional[str | float]
    price_updated: Optional[datetime] = None


class ReturnFlight(BaseModel):
    outbound: Flight
    inbound: Flight
    summary_price: float
    summary_currency: str
    previous_price: str | float


class DailyFare(BaseModel):
    """A single day's cheapest fare from /cheapestPerDay."""

    day: datetime
    departure_date: Optional[datetime]
    arrival_date: Optional[datetime]
    price: Optional[float]
    currency: Optional[str]
    sold_out: bool
    unavailable: bool


class TimetableFlight(BaseModel):
    """A scheduled (no-price) flight from /timtbl."""

    carrier_code: str
    flight_number: str
    departure_time: str
    arrival_time: str


class ReturnDailyFares(BaseModel):
    """Cheapest fare per day for outbound and inbound legs of a return trip."""

    outbound: list["DailyFare"]
    inbound: list["DailyFare"]


class AirportRoute(BaseModel):
    """An ``airport:XXX`` entry from a NetworkAirport.routes string."""

    kind: str = "airport"
    iata_code: str


class CityRoute(BaseModel):
    """A ``city:NAME`` entry."""

    kind: str = "city"
    code: str


class CountryRoute(BaseModel):
    """A ``country:xx`` entry (lowercase iso2)."""

    kind: str = "country"
    code: str


class RegionRoute(BaseModel):
    """A ``region:NAME`` entry."""

    kind: str = "region"
    code: str


Route = AirportRoute | CityRoute | CountryRoute | RegionRoute


def _parse_route(raw: str) -> Optional[Route]:
    """Parse a single ``kind:value`` route string. Unknown kinds return None."""
    if ":" not in raw:
        return None
    kind, _, value = raw.partition(":")
    if kind == "airport":
        return AirportRoute(iata_code=value)
    if kind == "city":
        return CityRoute(code=value)
    if kind == "country":
        return CountryRoute(code=value)
    if kind == "region":
        return RegionRoute(code=value)
    return None


class NetworkAirport(BaseModel):
    iata_code: str
    name: str
    seo_name: str
    country_code: str
    city_code: str
    region_code: Optional[str] = None
    currency_code: str
    time_zone: str
    base: bool
    latitude: float
    longitude: float
    routes: list[str]
    seasonal_routes: list[str]
    categories: list[str]
    aliases: list[str]
    priority: Optional[int] = None

    def typed_routes(self) -> list[Route]:
        """Parse ``routes`` strings into a typed discriminated union."""
        return [r for r in (_parse_route(s) for s in self.routes) if r is not None]

    def airport_routes(self) -> list[str]:
        """Just the IATA codes of airports reachable from here."""
        return [r.iata_code for r in self.typed_routes() if isinstance(r, AirportRoute)]

    def country_routes(self) -> list[str]:
        """Just the iso2 country codes reachable from here."""
        return [r.code for r in self.typed_routes() if isinstance(r, CountryRoute)]

    def typed_seasonal_routes(self) -> list[Route]:
        """Parse ``seasonal_routes`` strings into a typed discriminated union."""
        return [r for r in (_parse_route(s) for s in self.seasonal_routes) if r is not None]

    def seasonal_airport_routes(self) -> list[str]:
        """IATA codes reachable only seasonally (winter/summer schedule)."""
        return [
            r.iata_code
            for r in self.typed_seasonal_routes()
            if isinstance(r, AirportRoute)
        ]


class DestinationFare(BaseModel):
    """A reachable destination paired with its cheapest sampled fare, if any.

    ``fare`` is ``None`` when the destination is in the network but no fare
    came back from the price probe (no flights in the window, sold out, etc.).
    """

    airport: NetworkAirport
    fare: Optional[Flight] = None


class NetworkCountry(BaseModel):
    code: str
    iso3_code: str
    name: str
    currency: str
    default_airport_code: Optional[str] = None
    schengen: bool


class Network(BaseModel):
    """Live Ryanair network metadata from the aggregate endpoint."""

    airports: list[NetworkAirport]
    countries: list[NetworkCountry]
    cities: list[Dict[str, Any]]
    regions: list[Dict[str, Any]]


class FlightSearchParams(BaseModel):
    """What a one-way flight search looks like in Flyan terms.

    Validation here is syntactic. Network membership (does Ryanair fly this
    route today?) is :meth:`flyan.RyanAir.validate_route`.
    """

    from_airport: str
    from_date: datetime
    to_date: datetime
    destination_country: Optional[str] = None
    max_price: Optional[int] = None
    to_airport: Optional[str] = None
    departure_time_from: Optional[str] = "00:00"
    departure_time_to: Optional[str] = "23:59"

    @field_validator("from_airport", "to_airport")
    @classmethod
    def validate_iata(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        upper = v.upper()
        if not _IATA_PATTERN.fullmatch(upper):
            raise ValueError("Airport code must be a 3-letter IATA code")
        return upper

    @field_validator("from_date", "to_date")
    @classmethod
    def validate_dates(cls, v: datetime) -> datetime:
        if v < datetime.now():
            raise ValueError("Date from or to cannot be in the past")
        return v

    @field_validator("max_price")
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Price can't be negative")
        return v


class ReturnFlightSearchParams(FlightSearchParams):
    """What a return flight search looks like in Flyan terms."""

    return_date_from: datetime
    return_date_to: datetime
    inbound_departure_time_from: Optional[str] = "00:00"
    inbound_departure_time_to: Optional[str] = "23:59"
