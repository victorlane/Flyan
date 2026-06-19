"""
Local price-history tracker.

Ryanair does not expose a price-history endpoint. This module records
snapshots of :meth:`flyan.RyanAir.get_cheapest_per_day` to a JSONL file
keyed by (origin, destination), then reports whether the current cheapest
price is above or below the trailing N-day average.

A snapshot is one row per route per day. Re-snapshotting on the same day
appends another row; the analysis treats the most recent row per
(route, departure-date) as authoritative for "today's price."
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from .ryanair import RyanAir


@dataclass
class PriceAnomaly:
    """How today's price compares to a trailing window."""

    origin: str
    destination: str
    departure_date: datetime
    current_price: float
    average_price: float
    samples: int
    deviation_pct: float

    @property
    def is_deal(self) -> bool:
        """True when today's price is meaningfully below the trailing average."""
        return self.deviation_pct <= -10.0

    @property
    def is_spike(self) -> bool:
        """True when today's price is meaningfully above the trailing average."""
        return self.deviation_pct >= 10.0


class PriceTracker:
    """Append snapshots and query trailing averages from a local JSONL store.

    :param path: file to read/write. Parents are created on first write.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def snapshot(
        self,
        client: RyanAir,
        origin: str,
        destination: str,
        month: datetime,
        taken_at: Optional[datetime] = None,
    ) -> int:
        """Record every priced day of ``cheapest_per_day`` for one route+month.

        Returns the number of rows written.
        """
        taken_at = taken_at or datetime.now()
        daily = client.get_cheapest_per_day(origin, destination, month)
        rows = []
        for fare in daily:
            if fare.price is None:
                continue
            rows.append(
                {
                    "taken_at": taken_at.isoformat(),
                    "origin": origin.upper(),
                    "destination": destination.upper(),
                    "departure_date": fare.day.date().isoformat(),
                    "price": fare.price,
                    "currency": fare.currency,
                }
            )
        if not rows:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return len(rows)

    def _iter_rows(self) -> Iterable[dict]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def analyse(
        self,
        origin: str,
        destination: str,
        departure_date: datetime,
        window_days: int = 30,
    ) -> Optional[PriceAnomaly]:
        """Compare the most recent snapshot to the trailing ``window_days`` average.

        Returns ``None`` if there is no current price or fewer than 3 historical
        samples within the window.
        """
        origin = origin.upper()
        destination = destination.upper()
        target_date = departure_date.date().isoformat()
        cutoff = datetime.now() - timedelta(days=window_days)

        relevant: list[tuple[datetime, float, str]] = []
        for row in self._iter_rows():
            if row["origin"] != origin or row["destination"] != destination:
                continue
            if row["departure_date"] != target_date:
                continue
            try:
                taken_at = datetime.fromisoformat(row["taken_at"])
            except ValueError:
                continue
            if taken_at < cutoff:
                continue
            relevant.append((taken_at, float(row["price"]), row["currency"]))

        if len(relevant) < 3:
            return None
        relevant.sort(key=lambda t: t[0])
        current_price = relevant[-1][1]
        historical = [p for _, p, _ in relevant[:-1]]
        if not historical:
            return None
        average = statistics.fmean(historical)
        if average == 0:
            return None
        deviation = (current_price - average) / average * 100.0
        return PriceAnomaly(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            current_price=current_price,
            average_price=average,
            samples=len(historical),
            deviation_pct=round(deviation, 2),
        )
