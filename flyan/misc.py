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
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Could not find {filename} in {current_dir}. "
            f"Make sure the JSON files are included in the package."
        )


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
