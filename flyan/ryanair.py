"""
Ryanair client — coordinates the transport and parsers behind a small,
domain-friendly interface.

Endpoint method = (build URL + params) → transport.get_json or iter_fare_pages
→ parser. Each method is a few lines because the depth lives behind the
seams (``flyan.transport`` and ``flyan.wire``).

Error contract: an empty list means "the API answered, but no fares matched
your search". Anything else — network, status, decode, schema — raises
``RyanairException``. Callers that need to distinguish transient from
permanent failures should inspect the exception chain.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from .misc import (
    DailyFare,
    Flight,
    FlightSearchParams,
    Network,
    ReturnFlight,
    ReturnFlightSearchParams,
    TimetableFlight,
    currencies,
)
from .transport import RyanairException, RyanairTransport, Transport
from .wire import (
    parse_daily_fare,
    parse_flight,
    parse_network,
    parse_return_flight,
    parse_timetable_flight,
    serialize_search_params,
)

logger = logging.getLogger("Flyan")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)s:%(message)s",
            datefmt="%Y-%m-%d %I:%M:%S",
        )
    )
    logger.addHandler(handler)


_BASE = "https://services-api.ryanair.com/farfnd/v4"
_SCHEDULES = "https://services-api.ryanair.com/timtbl/3/schedules"
_AGGREGATE = "https://www.ryanair.com/api/views/locate/3/aggregate/all/en"


class RyanAir:
    """
    Ryanair flight-search client.

    :param currency: Preferred currency (ISO 4217). Sent as a query param so
        prices come back in this currency regardless of departure-airport locale.
    :param transport: Inject a custom :class:`Transport` (e.g. for recorded
        fixtures or tests). Defaults to a fresh :class:`RyanairTransport`.
    """

    def __init__(
        self,
        currency: str = "EUR",
        transport: Optional[Transport] = None,
    ):
        self.currency = currency if currency in currencies else "EUR"
        self.transport: Transport = transport or RyanairTransport()

    # --- lifecycle --------------------------------------------------------

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "RyanAir":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- fare searches ----------------------------------------------------

    def get_oneways(self, params: FlightSearchParams) -> list[Flight]:
        """Cheapest one-way fares in the given date window.

        Returns ``[]`` only when the API answered with no matching fares.
        Raises :class:`RyanairException` on transport or schema failure.
        """
        flights: list[Flight] = []
        url = f"{_BASE}/oneWayFares"
        wire = serialize_search_params(params, currency=self.currency)
        try:
            for page in self.transport.iter_fare_pages(url, wire):
                flights.extend(parse_flight(f["outbound"]) for f in page.get("fares", []))
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected one-way fare shape: {exc}") from exc
        return flights

    def get_returns(self, params: ReturnFlightSearchParams) -> list[ReturnFlight]:
        """Cheapest round-trip fares for two date windows."""
        flights: list[ReturnFlight] = []
        url = f"{_BASE}/roundTripFares"
        wire = serialize_search_params(params, currency=self.currency)
        try:
            for page in self.transport.iter_fare_pages(url, wire):
                flights.extend(parse_return_flight(f) for f in page.get("fares", []))
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected return fare shape: {exc}") from exc
        return flights

    def get_cheapest_per_day(
        self, origin: str, destination: str, month: datetime
    ) -> list[DailyFare]:
        """Daily cheapest fare for one route across one calendar month."""
        url = f"{_BASE}/oneWayFares/{origin.upper()}/{destination.upper()}/cheapestPerDay"
        params = {
            "outboundMonthOfDate": month.strftime("%Y-%m-01"),
            "currency": self.currency,
        }
        data = self.transport.get_json(url, params)
        try:
            fares = data.get("outbound", {}).get("fares", [])
            return [parse_daily_fare(f) for f in fares]
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected cheapestPerDay shape: {exc}") from exc

    def get_schedule(
        self, origin: str, destination: str, year: int, month: int
    ) -> list[TimetableFlight]:
        """Published timetable for one route. No prices; days with no service omitted."""
        url = f"{_SCHEDULES}/{origin.upper()}/{destination.upper()}/years/{year}/months/{month}"
        data = self.transport.get_json(url)
        try:
            return [
                parse_timetable_flight(f)
                for day in data.get("days", [])
                for f in day.get("flights", [])
            ]
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected schedule shape: {exc}") from exc

    def get_network(self) -> Network:
        """Live airport / country / city / region metadata."""
        data = self.transport.get_json(_AGGREGATE)
        try:
            return parse_network(data)
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected network shape: {exc}") from exc

    # --- convenience ------------------------------------------------------

    def validate_route(self, origin: str, destination: str) -> bool:
        """True if Ryanair currently flies ``origin`` → ``destination``.

        Hits the live network; cache the result if you need to call it
        repeatedly.
        """
        network = self.get_network()
        origin = origin.upper()
        destination = destination.upper()
        for airport in network.airports:
            if airport.iata_code != origin:
                continue
            return f"airport:{destination}" in airport.routes
        return False


__all__ = ["RyanAir", "RyanairException"]
