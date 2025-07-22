"""
Flyan - An open-source unofficial API wrapper to get flight data from Ryanair.
"""

from .ryanair import RyanAir, RyanairException
from .misc import (
    Airport,
    Flight,
    FlightSearchParams,
    ReturnFlight,
    ReturnFlightSearchParams,
)

__version__ = "0.1.5"
__all__ = [
    "RyanAir",
    "RyanairException",
    "Airport",
    "Flight",
    "FlightSearchParams",
    "ReturnFlight",
    "ReturnFlightSearchParams",
]
