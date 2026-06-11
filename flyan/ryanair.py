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
from datetime import datetime, timedelta
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
from .transport import RyanairException, RyanairTransport, Transport
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


def _months_between(start: datetime, end: datetime) -> list[datetime]:
    """First-of-month datetimes covering [start, end] inclusive."""
    cur = datetime(start.year, start.month, 1)
    last = datetime(end.year, end.month, 1)
    out: list[datetime] = []
    while cur <= last:
        out.append(cur)
        if cur.month == 12:
            cur = datetime(cur.year + 1, 1, 1)
        else:
            cur = datetime(cur.year, cur.month + 1, 1)
    return out


class RyanAir:
    """
    Ryanair flight-search client.

    :param currency: Preferred currency (ISO 4217). Sent as a query param so
        prices come back in this currency regardless of departure-airport locale.
    :param transport: Inject a custom :class:`Transport` (e.g. a
        :class:`CachingTransport` wrapping the default, or a fixture transport
        for tests). Defaults to a fresh :class:`RyanairTransport`.
    """

    def __init__(
        self,
        currency: str = "EUR",
        transport: Optional[Transport] = None,
    ):
        self.currency = currency if currency in currencies else "EUR"
        self.transport: Transport = transport or RyanairTransport()

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "RyanAir":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

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

    def get_cheapest_returns_per_day(
        self,
        origin: str,
        destination: str,
        outbound_month: datetime,
        inbound_month: Optional[datetime] = None,
        duration_from: int = 1,
        duration_to: int = 14,
    ) -> ReturnDailyFares:
        """Daily cheapest fare for a return trip, outbound and inbound side-by-side.

        ``duration_from``/``duration_to`` constrain the trip length in days.
        """
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
        data = self.transport.get_json(url, params)
        try:
            return parse_return_daily_fares(data)
        except (KeyError, ValueError) as exc:
            raise RyanairException(
                f"unexpected return cheapestPerDay shape: {exc}"
            ) from exc

    def get_active_dates(self, origin: str, destination: str) -> list[datetime]:
        """Dates on which the route is currently bookable. No price info, very cheap."""
        url = (
            f"{_BASE}/oneWayFares/{origin.upper()}/"
            f"{destination.upper()}/availabilities"
        )
        data = self.transport.get_json(url)
        return parse_availabilities(data)

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

    def get_destinations(self, origin: str) -> list[NetworkAirport]:
        """Every airport currently reachable from ``origin`` as a direct flight."""
        origin = origin.upper()
        net = self.get_network()
        origin_airport = next(
            (a for a in net.airports if a.iata_code == origin), None
        )
        if origin_airport is None:
            return []
        reachable = set(origin_airport.airport_routes())
        return [a for a in net.airports if a.iata_code in reachable]

    def get_destinations_in_country(
        self, origin: str, country_code: str
    ) -> list[NetworkAirport]:
        """Reachable airports from ``origin`` filtered to one country."""
        country = country_code.lower()
        return [a for a in self.get_destinations(origin) if a.country_code == country]

    def validate_route(self, origin: str, destination: str) -> bool:
        """True if Ryanair currently flies ``origin`` → ``destination``.

        Hits the live network; wrap the transport in :class:`CachingTransport`
        if you call this repeatedly.
        """
        network = self.get_network()
        origin = origin.upper()
        destination = destination.upper()
        for airport in network.airports:
            if airport.iata_code != origin:
                continue
            return destination in set(airport.airport_routes())
        return False

    def find_anywhere_under(
        self,
        origin: str,
        max_price: int,
        from_date: datetime,
        to_date: datetime,
    ) -> list[Flight]:
        """Cheapest flights from ``origin`` to anywhere, under ``max_price``."""
        return self.get_oneways(
            FlightSearchParams(
                from_airport=origin,
                from_date=from_date,
                to_date=to_date,
                max_price=max_price,
            )
        )

    def cheapest_weekend(
        self,
        origin: str,
        destination: str,
        months_ahead: int = 3,
        weekend_length: int = 2,
    ) -> Optional[tuple[DailyFare, DailyFare]]:
        """Cheapest Fri→Sun (or Fri→Mon) return for the next ``months_ahead`` months.

        Returns the (outbound, inbound) :class:`DailyFare` pair, or ``None`` if
        no priced weekend exists in the window.
        """
        if weekend_length not in (2, 3):
            raise ValueError("weekend_length must be 2 (Fri-Sun) or 3 (Fri-Mon)")
        now = datetime.now()
        end = now + timedelta(days=31 * months_ahead)
        months = _months_between(now, end)

        outbounds: list[DailyFare] = []
        inbounds: list[DailyFare] = []
        for m in months:
            pair = self.get_cheapest_returns_per_day(
                origin, destination, m, m,
                duration_from=weekend_length, duration_to=weekend_length,
            )
            outbounds.extend(pair.outbound)
            inbounds.extend(pair.inbound)

        # Index inbounds by day for O(1) match.
        inbound_by_day = {d.day.date(): d for d in inbounds if d.price is not None}

        best: Optional[tuple[DailyFare, DailyFare, float]] = None
        for out in outbounds:
            if out.price is None or out.day.weekday() != 4:  # 4 = Friday
                continue
            ret_date = (out.day + timedelta(days=weekend_length)).date()
            ret = inbound_by_day.get(ret_date)
            if ret is None or ret.price is None:
                continue
            total = out.price + ret.price
            if best is None or total < best[2]:
                best = (out, ret, total)

        return (best[0], best[1]) if best else None


__all__ = ["RyanAir", "RyanairException"]
