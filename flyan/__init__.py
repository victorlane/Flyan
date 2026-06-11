"""
Flyan - An open-source unofficial API wrapper to get flight data from Ryanair.
"""

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
from .ryanair import RyanAir
from .transport import RyanairException, RyanairTransport, Transport

__version__ = "0.2.0"  # x-release-please-version
__all__ = [
    "RyanAir",
    "RyanairException",
    "RyanairTransport",
    "Transport",
    "Airport",
    "DailyFare",
    "Flight",
    "FlightSearchParams",
    "Network",
    "NetworkAirport",
    "NetworkCountry",
    "ReturnFlight",
    "ReturnFlightSearchParams",
    "TimetableFlight",
]
