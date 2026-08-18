"""MCP server tests: client construction, tool registration, response shaping.

The tools are exercised against a stub RyanAir so nothing hits the network.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime
from typing import Any

import pytest

import flyan.mcp_server as mcp_server
from flyan.misc import DailyFare, NetworkAirport
from flyan.wire import parse_flight, parse_network_airport
from tests.fixtures import NETWORK_AIRPORT_DUB, one_way_fare

EXPECTED_TOOLS = [
    "find_flights",
    "find_anywhere_under",
    "explore_destinations",
    "cheapest_per_day",
]


class StubClient:
    """Records the call the tool made and returns whatever the test set up."""

    def __init__(self, **returns: Any) -> None:
        self._returns = returns
        self.calls: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self._returns.get(name, [])

        return method


@pytest.fixture
def stub_client(monkeypatch: pytest.MonkeyPatch):
    """Swap ``_get_client`` for a stub and hand it back to the test."""

    def install(**returns: Any) -> StubClient:
        client = StubClient(**returns)
        monkeypatch.setattr(mcp_server, "_get_client", lambda: client)
        return client

    return install


def _airport(**overrides) -> NetworkAirport:
    return parse_network_airport({**NETWORK_AIRPORT_DUB, **overrides})


def _reset_client(monkeypatch):
    """Each test needs a fresh _client so _get_client() actually builds one."""
    monkeypatch.setattr(mcp_server, "_client", None)


def test_get_client_defaults_to_eur(monkeypatch):
    _reset_client(monkeypatch)
    monkeypatch.delenv("FLYAN_CURRENCY", raising=False)

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        mcp_server,
        "RyanAir",
        lambda *, currency: captured.setdefault("currency", currency) or object(),
    )

    mcp_server._get_client()
    assert captured["currency"] == "EUR"


def test_get_client_respects_flyan_currency_env_var(monkeypatch):
    _reset_client(monkeypatch)
    monkeypatch.setenv("FLYAN_CURRENCY", "GBP")

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        mcp_server,
        "RyanAir",
        lambda *, currency: captured.setdefault("currency", currency) or object(),
    )

    mcp_server._get_client()
    assert captured["currency"] == "GBP"


def test_get_client_is_memoised(monkeypatch):
    _reset_client(monkeypatch)
    builds: list[int] = []
    monkeypatch.setattr(
        mcp_server,
        "RyanAir",
        lambda *, currency: builds.append(1) or object(),
    )

    first = mcp_server._get_client()
    second = mcp_server._get_client()

    assert first is second
    assert len(builds) == 1


def _list_tools() -> list:
    tools = mcp_server.mcp.list_tools()
    if inspect.isawaitable(tools):  # mcp < 2.0 exposed list_tools as async
        tools = asyncio.run(tools)
    return tools


def _input_schema(tool) -> dict:
    schema = getattr(tool, "inputSchema", None)
    if schema is None:  # mcp >= 2.0 renamed the field to input_schema
        schema = tool.input_schema
    return schema


def test_registers_exactly_the_expected_tools():
    assert [t.name for t in _list_tools()] == EXPECTED_TOOLS


def test_every_registered_tool_is_documented():
    assert all(t.description for t in _list_tools())


@pytest.mark.parametrize(
    "tool_name, required",
    [
        ("find_flights", {"from_airport", "from_date", "to_date"}),
        ("find_anywhere_under", {"from_airport", "max_price", "from_date", "to_date"}),
        ("explore_destinations", {"origin"}),
        ("cheapest_per_day", {"origin", "destination", "month"}),
    ],
)
def test_tool_schemas_require_the_right_arguments(tool_name: str, required: set):
    tool = next(t for t in _list_tools() if t.name == tool_name)
    assert set(_input_schema(tool).get("required", [])) == required


def test_find_flights_calls_get_oneways_with_parsed_params(stub_client):
    client = stub_client(get_oneways=[])

    mcp_server.find_flights(
        from_airport="DUB",
        from_date="2099-07-01",
        to_date="2099-07-08",
        to_airport="BCN",
        max_price=150,
    )

    name, (params,), _ = client.calls[0]
    assert name == "get_oneways"
    assert params.from_airport == "DUB"
    assert params.to_airport == "BCN"
    assert params.from_date == datetime(2099, 7, 1)
    assert params.to_date == datetime(2099, 7, 8)
    assert params.max_price == 150


def test_find_flights_lowercases_the_destination_country(stub_client):
    client = stub_client(get_oneways=[])

    mcp_server.find_flights(
        from_airport="DUB",
        from_date="2099-07-01",
        to_date="2099-07-08",
        destination_country="ES",
    )

    _, (params,), _ = client.calls[0]
    assert params.destination_country == "es"


def test_find_flights_trims_the_flight_to_agent_sized_fields(stub_client):
    stub_client(get_oneways=[parse_flight(one_way_fare())])

    result = mcp_server.find_flights(
        from_airport="DUB", from_date="2099-07-01", to_date="2099-07-08"
    )

    assert result == [
        {
            "flight_number": "FR6395",
            "from": "DUB",
            "from_name": "Dublin",
            "to": "BCN",
            "to_name": "Barcelona",
            "to_country": "es",
            "departure": "2026-07-02T21:50:00",
            "arrival": "2026-07-03T01:20:00",
            "price": 82.31,
            "currency": "EUR",
        }
    ]


def test_find_anywhere_under_forwards_its_arguments(stub_client):
    client = stub_client(find_anywhere_under=[])

    mcp_server.find_anywhere_under(
        from_airport="STN", max_price=50, from_date="2099-08-01", to_date="2099-08-03"
    )

    name, _, kwargs = client.calls[0]
    assert name == "find_anywhere_under"
    assert kwargs["origin"] == "STN"
    assert kwargs["max_price"] == 50
    assert kwargs["from_date"] == datetime(2099, 8, 1)
    assert kwargs["to_date"] == datetime(2099, 8, 3)


def test_find_anywhere_under_trims_the_same_flight_shape(stub_client):
    stub_client(find_anywhere_under=[parse_flight(one_way_fare("EDI", "Edinburgh", "gb"))])

    result = mcp_server.find_anywhere_under(
        from_airport="DUB", max_price=50, from_date="2099-08-01", to_date="2099-08-03"
    )

    assert result[0]["to"] == "EDI"
    assert result[0]["to_country"] == "gb"


def test_explore_destinations_groups_and_trims(stub_client):
    client = stub_client(
        explore_by_country={
            "ie": [_airport()],
            "gb": [_airport(iataCode="STN", name="London Stansted", regionCode=None)],
        }
    )

    result = mcp_server.explore_destinations("DUB")

    assert client.calls[0][0] == "explore_by_country"
    assert result["ie"] == [
        {"iata": "DUB", "name": "Dublin", "city": "DUBLIN", "region": "LEINSTER"}
    ]
    assert result["gb"][0]["region"] == ""


def test_cheapest_per_day_forwards_the_month_and_trims_fares(stub_client):
    client = stub_client(
        get_cheapest_per_day=[
            DailyFare(
                day=datetime(2026, 7, 1),
                departure_date=datetime(2026, 7, 1, 19, 35),
                arrival_date=datetime(2026, 7, 1, 23, 5),
                price=45.99,
                currency="EUR",
                sold_out=False,
                unavailable=False,
            ),
            DailyFare(
                day=datetime(2026, 7, 2),
                departure_date=None,
                arrival_date=None,
                price=None,
                currency=None,
                sold_out=True,
                unavailable=False,
            ),
        ]
    )

    result = mcp_server.cheapest_per_day("DUB", "BCN", "2026-07-01")

    name, _, kwargs = client.calls[0]
    assert name == "get_cheapest_per_day"
    assert kwargs["month"] == datetime(2026, 7, 1)
    assert result == [
        {
            "day": "2026-07-01",
            "price": 45.99,
            "currency": "EUR",
            "departure": "2026-07-01T19:35:00",
            "sold_out": False,
            "unavailable": False,
        },
        {
            "day": "2026-07-02",
            "price": None,
            "currency": None,
            "departure": None,
            "sold_out": True,
            "unavailable": False,
        },
    ]
