"""
Flyan - An open-source unofficial API wrapper to get flight data from Ryanair.
"""

from .ryanair import RyanAir, RyanairException
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

__version__ = "0.2.0"  # x-release-please-version
__all__ = [
    "RyanAir",
    "RyanairException",
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
