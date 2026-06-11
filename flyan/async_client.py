"""
Async Ryanair client. Mirrors :class:`flyan.RyanAir` method-for-method but
returns awaitables, so callers can fan out multiple searches concurrently
with ``asyncio.gather``.

The transport seam is the same; an :class:`AsyncRyanAir` accepts any
:class:`AsyncTransport`. The live adapter is :class:`AsyncRyanairTransport`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .misc import (
    DailyFare,
    Flight,
    FlightSearchParams,
    Network,
    NetworkAirport,
    ReturnDailyFares,
    ReturnFlight,
    ReturnFlightSearchParams,
    TimetableFlight,
    currencies,
)
from .transport import (
    AsyncRyanairTransport,
    AsyncTransport,
    RyanairException,
)
from .wire import (
    parse_availabilities,
    parse_daily_fare,
    parse_flight,
    parse_network,
    parse_return_daily_fares,
    parse_return_flight,
    parse_timetable_flight,
    serialize_search_params,
)

_BASE = "https://services-api.ryanair.com/farfnd/v4"
_SCHEDULES = "https://services-api.ryanair.com/timtbl/3/schedules"
_AGGREGATE = "https://www.ryanair.com/api/views/locate/3/aggregate/all/en"


class AsyncRyanAir:
    """Async Ryanair flight-search client."""

    def __init__(
        self,
        currency: str = "EUR",
        transport: Optional[AsyncTransport] = None,
    ):
        self.currency = currency if currency in currencies else "EUR"
        self.transport: AsyncTransport = transport or AsyncRyanairTransport()

    async def aclose(self) -> None:
        await self.transport.aclose()

    async def __aenter__(self) -> "AsyncRyanAir":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def get_oneways(self, params: FlightSearchParams) -> list[Flight]:
        flights: list[Flight] = []
        url = f"{_BASE}/oneWayFares"
        wire = serialize_search_params(params, currency=self.currency)
        try:
            async for page in self.transport.iter_fare_pages(url, wire):
                flights.extend(parse_flight(f["outbound"]) for f in page.get("fares", []))
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected one-way fare shape: {exc}") from exc
        return flights

    async def get_returns(
        self, params: ReturnFlightSearchParams
    ) -> list[ReturnFlight]:
        flights: list[ReturnFlight] = []
        url = f"{_BASE}/roundTripFares"
        wire = serialize_search_params(params, currency=self.currency)
        try:
            async for page in self.transport.iter_fare_pages(url, wire):
                flights.extend(parse_return_flight(f) for f in page.get("fares", []))
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected return fare shape: {exc}") from exc
        return flights

    async def get_cheapest_per_day(
        self, origin: str, destination: str, month: datetime
    ) -> list[DailyFare]:
        url = f"{_BASE}/oneWayFares/{origin.upper()}/{destination.upper()}/cheapestPerDay"
        params = {
            "outboundMonthOfDate": month.strftime("%Y-%m-01"),
            "currency": self.currency,
        }
        data = await self.transport.get_json(url, params)
        try:
            fares = data.get("outbound", {}).get("fares", [])
            return [parse_daily_fare(f) for f in fares]
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected cheapestPerDay shape: {exc}") from exc

    async def get_cheapest_returns_per_day(
        self,
        origin: str,
        destination: str,
        outbound_month: datetime,
        inbound_month: Optional[datetime] = None,
        duration_from: int = 1,
        duration_to: int = 14,
    ) -> ReturnDailyFares:
        url = (
            f"{_BASE}/roundTripFares/"
            f"{origin.upper()}/{destination.upper()}/cheapestPerDay"
        )
        params = {
            "outboundMonthOfDate": outbound_month.strftime("%Y-%m-01"),
            "inboundMonthOfDate": (inbound_month or outbound_month).strftime("%Y-%m-01"),
            "durationFrom": duration_from,
            "durationTo": duration_to,
            "currency": self.currency,
        }
        data = await self.transport.get_json(url, params)
        try:
            return parse_return_daily_fares(data)
        except (KeyError, ValueError) as exc:
            raise RyanairException(
                f"unexpected return cheapestPerDay shape: {exc}"
            ) from exc

    async def get_active_dates(
        self, origin: str, destination: str
    ) -> list[datetime]:
        url = (
            f"{_BASE}/oneWayFares/{origin.upper()}/"
            f"{destination.upper()}/availabilities"
        )
        data = await self.transport.get_json(url)
        return parse_availabilities(data)

    async def get_schedule(
        self, origin: str, destination: str, year: int, month: int
    ) -> list[TimetableFlight]:
        url = f"{_SCHEDULES}/{origin.upper()}/{destination.upper()}/years/{year}/months/{month}"
        data = await self.transport.get_json(url)
        try:
            return [
                parse_timetable_flight(f)
                for day in data.get("days", [])
                for f in day.get("flights", [])
            ]
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected schedule shape: {exc}") from exc

    async def get_network(self) -> Network:
        data = await self.transport.get_json(_AGGREGATE)
        try:
            return parse_network(data)
        except (KeyError, ValueError) as exc:
            raise RyanairException(f"unexpected network shape: {exc}") from exc

    async def get_destinations(self, origin: str) -> list[NetworkAirport]:
        origin = origin.upper()
        net = await self.get_network()
        origin_airport = next(
            (a for a in net.airports if a.iata_code == origin), None
        )
        if origin_airport is None:
            return []
        reachable = set(origin_airport.airport_routes())
        return [a for a in net.airports if a.iata_code in reachable]

    async def validate_route(self, origin: str, destination: str) -> bool:
        net = await self.get_network()
        origin = origin.upper()
        destination = destination.upper()
        for airport in net.airports:
            if airport.iata_code != origin:
                continue
            return destination in set(airport.airport_routes())
        return False
