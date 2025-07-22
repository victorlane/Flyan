import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, field_validator
from importlib.resources import files


def _load_json_file(filename: str) -> Dict[str, Any]:
    """Load JSON file from the package resources."""
    try:
        # importlib.resources import for installed package
        package_files = files("flyan")
        json_file = package_files / filename

        if json_file.is_file():
            content = json_file.read_text(encoding="utf-8")
            return json.loads(content)
    except Exception:
        pass

    # Fallback to file system approach for development/local imports
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
stations: Dict[str, Any] = _load_json_file("stations.json")


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


class ReturnFlight(BaseModel):
    outbound: Flight
    inbound: Flight
    summary_price: float
    summary_currency: str
    previous_price: str | float


class FlightSearchParams(BaseModel):
    """Parameters for flight searches"""

    from_airport: str
    from_date: datetime
    to_date: datetime
    destination_country: Optional[str] = None
    max_price: Optional[int] = None
    to_airport: Optional[str] = None
    departure_time_from: Optional[str] = "00:00"
    departure_time_to: Optional[str] = "23:59"

    @field_validator("from_airport")
    def validate_airport(cls, v: str):

        if v not in stations.keys():
            raise ValueError("Airport code must be a 3-letter IATA code")

        return v.upper()

    @field_validator("from_date", "to_date")
    def validate_dates(cls, v: datetime):
        if v < datetime.now():
            raise ValueError("Date from or to cannot be in the past")

        return v

    @field_validator("max_price")
    def validate_price(cls, v: int | None):
        if v is None:
            return v

        if v <= 0:
            raise ValueError("Price can't be negative")

        return v

    def to_api_params(self) -> Dict[str, str | int]:
        """Convert the parameters to the format expected by the Ryanair API"""
        params: Dict[str, str | int] = {
            "departureAirportIataCode": self.from_airport,
            "outboundDepartureDateFrom": self.from_date.date().isoformat(),
            "outboundDepartureDateTo": self.to_date.date().isoformat(),
            "outboundDepartureTimeFrom": self.departure_time_from or "00:00",
            "outboundDepartureTimeTo": self.departure_time_to or "23:59",
        }

        if self.destination_country:
            params["arrivalCountryCode"] = self.destination_country

        if self.max_price:
            params["priceValueTo"] = self.max_price

        if self.to_airport:
            params["arrivalAirportIataCode"] = self.to_airport

        return params


class ReturnFlightSearchParams(FlightSearchParams):
    """Parameters for return flight searches"""

    return_date_from: datetime
    return_date_to: datetime
    inbound_departure_time_from: Optional[str] = "00:00"
    inbound_departure_time_to: Optional[str] = "23:59"

    @field_validator("return_date_from", "return_date_to")
    @classmethod
    def validate_return_dates(cls, v: datetime) -> datetime:
        # ideally use model_validator for cross-field validation
        return v

    def to_api_params(self) -> Dict[str, str | int]:
        """Convert the parameters to the format expected by the Ryanair API"""
        params = super().to_api_params()

        additional_params = {
            "inboundDepartureDateFrom": self.return_date_from.date().isoformat(),
            "inboundDepartureDateTo": self.return_date_to.date().isoformat(),
        }

        if self.inbound_departure_time_from:
            additional_params["inboundDepartureTimeFrom"] = (
                self.inbound_departure_time_from
            )
        if self.inbound_departure_time_to:
            additional_params["inboundDepartureTimeTo"] = self.inbound_departure_time_to

        params.update(additional_params)
        return params
