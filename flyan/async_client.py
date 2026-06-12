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
    DestinationFare,
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

    def _resolve_destinations(
        self, net: Network, origin: str, *, seasonal: bool = False
    ) -> list[NetworkAirport]:
        origin = origin.upper()
        origin_airport = next(
            (a for a in net.airports if a.iata_code == origin), None
        )
        if origin_airport is None:
            return []
        codes = (
            origin_airport.seasonal_airport_routes()
            if seasonal
            else origin_airport.airport_routes()
        )
        reachable = set(codes)
        return [a for a in net.airports if a.iata_code in reachable]

    async def get_destinations(self, origin: str) -> list[NetworkAirport]:
        return self._resolve_destinations(await self.get_network(), origin)

    async def get_destinations_in_country(
        self, origin: str, country_code: str
    ) -> list[NetworkAirport]:
        country = country_code.lower()
        return [a for a in await self.get_destinations(origin) if a.country_code == country]

    async def get_destinations_in_region(
        self, origin: str, region_code: str
    ) -> list[NetworkAirport]:
        region = region_code.upper()
        return [a for a in await self.get_destinations(origin) if a.region_code == region]

    async def get_destinations_in_city(
        self, origin: str, city_code: str
    ) -> list[NetworkAirport]:
        city = city_code.upper()
        return [a for a in await self.get_destinations(origin) if a.city_code == city]

    async def get_seasonal_destinations(self, origin: str) -> list[NetworkAirport]:
        return self._resolve_destinations(
            await self.get_network(), origin, seasonal=True
        )

    async def explore_by_country(
        self, origin: str
    ) -> dict[str, list[NetworkAirport]]:
        grouped: dict[str, list[NetworkAirport]] = {}
        for airport in await self.get_destinations(origin):
            grouped.setdefault(airport.country_code, []).append(airport)
        return grouped

    async def explore_by_region(
        self, origin: str
    ) -> dict[str, list[NetworkAirport]]:
        grouped: dict[str, list[NetworkAirport]] = {}
        for airport in await self.get_destinations(origin):
            grouped.setdefault(airport.region_code or "", []).append(airport)
        return grouped

    async def explore_with_fares(
        self,
        origin: str,
        from_date: datetime,
        to_date: datetime,
        max_price: Optional[int] = None,
    ) -> list[DestinationFare]:
        """Reachable destinations from ``origin`` joined to a cheapest-fare probe."""
        params = FlightSearchParams(
            from_airport=origin,
            from_date=from_date,
            to_date=to_date,
            max_price=max_price,
        )
        destinations = await self.get_destinations(origin)
        fares = await self.get_oneways(params)

        cheapest: dict[str, Flight] = {}
        for f in fares:
            code = f.arrival_airport.iata_code
            current = cheapest.get(code)
            if current is None or f.price < current.price:
                cheapest[code] = f

        return [
            DestinationFare(airport=a, fare=cheapest.get(a.iata_code))
            for a in destinations
        ]

    async def validate_route(self, origin: str, destination: str) -> bool:
        net = await self.get_network()
        origin = origin.upper()
        destination = destination.upper()
        for airport in net.airports:
            if airport.iata_code != origin:
                continue
            return destination in set(airport.airport_routes())
        return False
