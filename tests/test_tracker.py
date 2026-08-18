"""PriceTracker tests against a JSONL file in tmp_path. No network access."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from flyan.ryanair import RyanAir
from flyan.tracker import PriceAnomaly, PriceTracker
from tests.fakes import FakeTransport
from tests.fixtures import CHEAPEST_PER_DAY_RESPONSE, cheapest_per_day_url

DEPARTURE = datetime(2026, 7, 1)


def _anomaly(deviation: float) -> PriceAnomaly:
    return PriceAnomaly(
        origin="DUB",
        destination="BCN",
        departure_date=DEPARTURE,
        current_price=100.0,
        average_price=100.0,
        samples=5,
        deviation_pct=deviation,
    )


def _row(
    price: float,
    days_ago: float = 0.0,
    origin: str = "DUB",
    destination: str = "BCN",
    departure: datetime = DEPARTURE,
) -> dict:
    return {
        "taken_at": (datetime.now() - timedelta(days=days_ago)).isoformat(),
        "origin": origin,
        "destination": destination,
        "departure_date": departure.date().isoformat(),
        "price": price,
        "currency": "EUR",
    }


def _write(path: Path, *rows: dict) -> PriceTracker:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return PriceTracker(path)


@pytest.mark.parametrize(
    "deviation, is_deal, is_spike",
    [
        (-25.0, True, False),
        (-10.0, True, False),
        (-9.99, False, False),
        (0.0, False, False),
        (9.99, False, False),
        (10.0, False, True),
        (42.0, False, True),
    ],
)
def test_deal_and_spike_thresholds(deviation: float, is_deal: bool, is_spike: bool):
    anomaly = _anomaly(deviation)
    assert anomaly.is_deal is is_deal
    assert anomaly.is_spike is is_spike


def _client() -> RyanAir:
    transport = FakeTransport({cheapest_per_day_url(): CHEAPEST_PER_DAY_RESPONSE})
    return RyanAir(transport=transport)


def test_snapshot_writes_one_row_per_priced_day(tmp_path: Path):
    store = tmp_path / "nested" / "prices.jsonl"
    tracker = PriceTracker(store)

    written = tracker.snapshot(_client(), "dub", "bcn", datetime(2026, 7, 1))

    assert written == 2  # the sold-out day carries no price
    rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    assert [r["departure_date"] for r in rows] == ["2026-07-01", "2026-07-03"]
    assert [r["price"] for r in rows] == [45.99, 61.50]


def test_snapshot_upper_cases_the_route(tmp_path: Path):
    store = tmp_path / "prices.jsonl"
    PriceTracker(store).snapshot(_client(), "dub", "bcn", datetime(2026, 7, 1))

    row = json.loads(store.read_text(encoding="utf-8").splitlines()[0])
    assert (row["origin"], row["destination"]) == ("DUB", "BCN")


def test_snapshot_stamps_the_supplied_taken_at(tmp_path: Path):
    store = tmp_path / "prices.jsonl"
    taken_at = datetime(2026, 6, 1, 12, 0, 0)

    PriceTracker(store).snapshot(_client(), "DUB", "BCN", datetime(2026, 7, 1), taken_at=taken_at)

    row = json.loads(store.read_text(encoding="utf-8").splitlines()[0])
    assert row["taken_at"] == taken_at.isoformat()


def test_snapshot_appends_instead_of_overwriting(tmp_path: Path):
    store = tmp_path / "prices.jsonl"
    tracker = PriceTracker(store)

    tracker.snapshot(_client(), "DUB", "BCN", datetime(2026, 7, 1))
    tracker.snapshot(_client(), "DUB", "BCN", datetime(2026, 7, 1))

    assert len(store.read_text(encoding="utf-8").splitlines()) == 4


def test_snapshot_writes_nothing_when_no_day_is_priced(tmp_path: Path):
    store = tmp_path / "prices.jsonl"
    transport = FakeTransport({cheapest_per_day_url(): {"outbound": {"fares": []}}})

    written = PriceTracker(store).snapshot(
        RyanAir(transport=transport), "DUB", "BCN", datetime(2026, 7, 1)
    )

    assert written == 0
    assert not store.exists()


def test_analyse_returns_none_without_a_store(tmp_path: Path):
    tracker = PriceTracker(tmp_path / "missing.jsonl")
    assert tracker.analyse("DUB", "BCN", DEPARTURE) is None


def test_analyse_needs_at_least_three_samples(tmp_path: Path):
    tracker = _write(
        tmp_path / "p.jsonl",
        _row(100.0, days_ago=3),
        _row(90.0, days_ago=2),
    )
    assert tracker.analyse("DUB", "BCN", DEPARTURE) is None


def test_analyse_compares_the_latest_price_to_the_trailing_mean(tmp_path: Path):
    tracker = _write(
        tmp_path / "p.jsonl",
        _row(100.0, days_ago=4),
        _row(120.0, days_ago=3),
        _row(80.0, days_ago=2),
        _row(75.0, days_ago=1),
    )

    anomaly = tracker.analyse("DUB", "BCN", DEPARTURE)

    assert anomaly is not None
    assert anomaly.current_price == 75.0
    assert anomaly.average_price == 100.0
    assert anomaly.samples == 3
    assert anomaly.deviation_pct == -25.0
    assert anomaly.is_deal is True


def test_analyse_reads_rows_in_timestamp_order_not_file_order(tmp_path: Path):
    tracker = _write(
        tmp_path / "p.jsonl",
        _row(50.0, days_ago=1),
        _row(100.0, days_ago=4),
        _row(100.0, days_ago=3),
        _row(100.0, days_ago=2),
    )

    anomaly = tracker.analyse("DUB", "BCN", DEPARTURE)

    assert anomaly is not None
    assert anomaly.current_price == 50.0


def test_analyse_accepts_lowercase_route_codes(tmp_path: Path):
    tracker = _write(
        tmp_path / "p.jsonl",
        _row(100.0, days_ago=3),
        _row(100.0, days_ago=2),
        _row(110.0, days_ago=1),
    )

    assert tracker.analyse("dub", "bcn", DEPARTURE) is not None


def test_analyse_ignores_rows_outside_the_window(tmp_path: Path):
    tracker = _write(
        tmp_path / "p.jsonl",
        _row(500.0, days_ago=90),
        _row(100.0, days_ago=3),
        _row(100.0, days_ago=2),
        _row(110.0, days_ago=1),
    )

    anomaly = tracker.analyse("DUB", "BCN", DEPARTURE, window_days=30)

    assert anomaly is not None
    assert anomaly.samples == 2
    assert anomaly.average_price == 100.0


def test_analyse_ignores_other_routes_and_departure_dates(tmp_path: Path):
    tracker = _write(
        tmp_path / "p.jsonl",
        _row(10.0, days_ago=3, destination="EDI"),
        _row(10.0, days_ago=3, origin="STN"),
        _row(10.0, days_ago=3, departure=datetime(2026, 7, 9)),
        _row(100.0, days_ago=3),
        _row(100.0, days_ago=2),
        _row(120.0, days_ago=1),
    )

    anomaly = tracker.analyse("DUB", "BCN", DEPARTURE)

    assert anomaly is not None
    assert anomaly.samples == 2
    assert anomaly.deviation_pct == 20.0
    assert anomaly.is_spike is True


def test_analyse_skips_corrupt_lines(tmp_path: Path):
    store = tmp_path / "p.jsonl"
    good = [_row(100.0, days_ago=3), _row(100.0, days_ago=2), _row(90.0, days_ago=1)]
    store.write_text(
        "\n".join(
            [
                json.dumps(good[0]),
                "{not json at all",
                "",
                json.dumps(good[1]),
                json.dumps({**_row(999.0), "taken_at": "not-a-timestamp"}),
                json.dumps(good[2]),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    anomaly = PriceTracker(store).analyse("DUB", "BCN", DEPARTURE)

    assert anomaly is not None
    assert anomaly.samples == 2
    assert anomaly.current_price == 90.0


def test_analyse_returns_none_when_the_trailing_average_is_zero(tmp_path: Path):
    tracker = _write(
        tmp_path / "p.jsonl",
        _row(0.0, days_ago=3),
        _row(0.0, days_ago=2),
        _row(50.0, days_ago=1),
    )

    assert tracker.analyse("DUB", "BCN", DEPARTURE) is None


def test_snapshot_then_analyse_round_trips(tmp_path: Path):
    store = tmp_path / "p.jsonl"
    tracker = PriceTracker(store)
    for days_ago in (3, 2, 1):
        tracker.snapshot(
            _client(),
            "DUB",
            "BCN",
            datetime(2026, 7, 1),
            taken_at=datetime.now() - timedelta(days=days_ago),
        )

    anomaly = tracker.analyse("DUB", "BCN", DEPARTURE)

    assert anomaly is not None
    assert anomaly.current_price == 45.99
    assert anomaly.deviation_pct == 0.0
