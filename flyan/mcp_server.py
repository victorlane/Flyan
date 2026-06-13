"""
MCP server for Flyan.

Exposes a small, agent-friendly slice of the Flyan API over the Model
Context Protocol so LLM clients (Claude Desktop, Cursor, Claude Code, etc.)
can search Ryanair fares from natural-language prompts like
"find me a cheap flight from Dublin to Spain in August under €150".

Run via the ``flyan-mcp`` console script registered in ``pyproject.toml``,
or directly with ``python -m flyan.mcp_server``.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .misc import Flight, FlightSearchParams
from .ryanair import RyanAir

mcp = FastMCP("flyan")

_client: Optional[RyanAir] = None


def _get_client() -> RyanAir:
    """Lazily build the RyanAir client so importing this module never hits the network.

    Reads the ``FLYAN_CURRENCY`` environment variable (default ``"EUR"``) and
    passes it to :class:`~flyan.ryanair.RyanAir` so agents can request prices
    in a currency other than EUR without editing the server source.  Set it
    before launching the MCP server, e.g.::

        FLYAN_CURRENCY=GBP flyan-mcp
    """
    global _client
    if _client is None:
        currency = os.environ.get("FLYAN_CURRENCY", "EUR")
        _client = RyanAir(currency=currency)
    return _client


def _flight_to_dict(f: Flight) -> dict[str, Any]:
    """Trim a Flight to the fields an agent actually needs.

    The full ``Flight`` model has nested ``Airport`` objects and metadata
    that bloats the agent's context. This keeps the response compact while
    preserving everything you need to recommend, book, or refine.
    """
    return {
        "flight_number": f.flight_number,
        "from": f.departure_airport.iata_code,
        "from_name": f.departure_airport.name,
        "to": f.arrival_airport.iata_code,
        "to_name": f.arrival_airport.name,
        "to_country": f.arrival_airport.city_country_code,
        "departure": f.departure_date.isoformat(),
        "arrival": f.arrival_date.isoformat(),
        "price": f.price,
        "currency": f.currency,
    }


@mcp.tool()
def find_flights(
    from_airport: str,
    from_date: str,
    to_date: str,
    to_airport: Optional[str] = None,
    destination_country: Optional[str] = None,
    max_price: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Search Ryanair one-way fares.

    ``from_airport`` and ``to_airport`` are 3-letter IATA codes (e.g. ``DUB``).
    ``destination_country`` is a lowercase ISO2 code (e.g. ``es``, ``gb``);
    uppercase silently returns no fares.

    Dates are ISO format (``YYYY-MM-DD``) and bound a *departure window*: the
    API returns the cheapest fare per route per day inside the window.
    """
    params = FlightSearchParams(
        from_airport=from_airport,
        from_date=datetime.fromisoformat(from_date),
        to_date=datetime.fromisoformat(to_date),
        to_airport=to_airport,
        destination_country=destination_country.lower() if destination_country else None,
        max_price=max_price,
    )
    flights = _get_client().get_oneways(params)
    return [_flight_to_dict(f) for f in flights]


@mcp.tool()
def find_anywhere_under(
    from_airport: str,
    max_price: int,
    from_date: str,
    to_date: str,
) -> list[dict[str, Any]]:
    """Cheapest fares from ``from_airport`` to *anywhere* under ``max_price``.

    Useful for "where can I go for under £50 this weekend" style prompts.
    """
    flights = _get_client().find_anywhere_under(
        origin=from_airport,
        max_price=max_price,
        from_date=datetime.fromisoformat(from_date),
        to_date=datetime.fromisoformat(to_date),
    )
    return [_flight_to_dict(f) for f in flights]


@mcp.tool()
def explore_destinations(origin: str) -> dict[str, list[dict[str, str]]]:
    """Every destination Ryanair flies to from ``origin``, grouped by country.

    Returns ``{country_code: [{iata, name, city, region}]}``. No fare lookup,
    just the network. Good for answering "what countries can I reach from X"
    or "does origin fly to destination at all".
    """
    grouped = _get_client().explore_by_country(origin)
    return {
        country: [
            {
                "iata": a.iata_code,
                "name": a.name,
                "city": a.city_code,
                "region": a.region_code or "",
            }
            for a in airports
        ]
        for country, airports in grouped.items()
    }


@mcp.tool()
def cheapest_per_day(
    origin: str,
    destination: str,
    month: str,
) -> list[dict[str, Any]]:
    """Cheapest fare per day for one route across a single calendar month.

    ``month`` is the first of the month in ISO format (``YYYY-MM-01``).
    Powers "what's the cheapest day in July to fly DUB->BCN" style prompts.
    Days with no flight or no price come back with ``price=None``.
    """
    fares = _get_client().get_cheapest_per_day(
        origin=origin,
        destination=destination,
        month=datetime.fromisoformat(month),
    )
    return [
        {
            "day": f.day.date().isoformat(),
            "price": f.price,
            "currency": f.currency,
            "departure": f.departure_date.isoformat() if f.departure_date else None,
            "sold_out": f.sold_out,
            "unavailable": f.unavailable,
        }
        for f in fares
    ]


def main() -> None:
    """Entry point for the ``flyan-mcp`` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
