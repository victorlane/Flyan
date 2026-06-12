"""
Flyan - An open-source unofficial API wrapper to get flight data from Ryanair.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from .async_client import AsyncRyanAir
from .misc import (
    Airport,
    AirportRoute,
    CityRoute,
    CountryRoute,
    DailyFare,
    DestinationFare,
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

try:
    __version__ = _pkg_version("Flyan")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
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
    "DestinationFare",
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
