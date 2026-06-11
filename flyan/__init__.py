"""
Flyan - An open-source unofficial API wrapper to get flight data from Ryanair.
"""

from .async_client import AsyncRyanAir
from .misc import (
    Airport,
    AirportRoute,
    CityRoute,
    CountryRoute,
    DailyFare,
    Flight,
    FlightSearchParams,
    Network,
    NetworkAirport,
    NetworkCountry,
    RegionRoute,
    ReturnDailyFares,
    ReturnFlight,
    ReturnFlightSearchParams,
    Route,
    TimetableFlight,
)
from .ryanair import RyanAir
from .tracker import PriceAnomaly, PriceTracker
from .transport import (
    AsyncRyanairTransport,
    AsyncTransport,
    CachingTransport,
    RyanairException,
    RyanairTransport,
    Transport,
)

__version__ = "0.2.0"  # x-release-please-version
__all__ = [
    "RyanAir",
    "AsyncRyanAir",
    "RyanairException",
    "RyanairTransport",
    "AsyncRyanairTransport",
    "CachingTransport",
    "Transport",
    "AsyncTransport",
    "PriceTracker",
    "PriceAnomaly",
    "Airport",
    "AirportRoute",
    "CityRoute",
    "CountryRoute",
    "DailyFare",
    "Flight",
    "FlightSearchParams",
    "Network",
    "NetworkAirport",
    "NetworkCountry",
    "RegionRoute",
    "ReturnDailyFares",
    "ReturnFlight",
    "ReturnFlightSearchParams",
    "Route",
    "TimetableFlight",
]
