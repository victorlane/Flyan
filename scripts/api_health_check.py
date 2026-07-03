#!/usr/bin/env python3
"""Live probe of the Ryanair endpoints Flyan depends on.

Ryanair's API has no contract, so shape changes break us silently. This
script (run daily by ``.github/workflows/api-health.yml``) fetches the
aggregate endpoint and a one-way fare search through Flyan's own transport
and asserts that the shapes ``flyan.wire`` expects still hold.

On any drift it writes a markdown report (``--report``) describing the
difference and exits non-zero, so the workflow can open an ``endpoint``
issue pointing at ``flyan/wire.py`` and ``docs/internal-api-spec.md``.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from flyan.misc import FlightSearchParams
from flyan.transport import RyanairTransport
from flyan.wire import parse_flight, parse_network, serialize_search_params

AGGREGATE_URL = "https://www.ryanair.com/api/views/locate/3/aggregate/all/en"
ONE_WAY_FARES_URL = "https://services-api.ryanair.com/farfnd/v4/oneWayFares"

AGGREGATE_KEYS = frozenset({"airports", "countries", "cities", "regions"})

# Fields parse_network_airport() reads unconditionally — losing any of these
# upstream means a KeyError for every get_network() caller.
AIRPORT_REQUIRED_FIELDS = (
    "iataCode",
    "name",
    "seoName",
    "countryCode",
    "cityCode",
    "currencyCode",
    "timeZone",
    "coordinates",
)

SAMPLE_AIRPORT = "DUB"
FARE_ORIGIN = "DUB"
FARE_DESTINATION = "BCN"
# Probe a date far enough out that the route is bookable but near enough
# that the schedule is published.
FARE_DAYS_AHEAD = 14


def check_aggregate(transport: RyanairTransport) -> List[str]:
    """Verify the aggregate endpoint's top-level shape and the DUB sample."""
    failures: List[str] = []
    raw = transport.get_json(AGGREGATE_URL)

    if not isinstance(raw, dict):
        return [f"aggregate: expected a JSON object, got `{type(raw).__name__}`"]

    missing = AGGREGATE_KEYS - raw.keys()
    if missing:
        failures.append(
            f"aggregate: missing top-level keys `{sorted(missing)}` "
            f"(expected `{sorted(AGGREGATE_KEYS)}`, got `{sorted(raw.keys())}`)"
        )
        return failures

    dub = next(
        (a for a in raw["airports"] if a.get("iataCode") == SAMPLE_AIRPORT), None
    )
    if dub is None:
        failures.append(
            f"aggregate: sample airport `{SAMPLE_AIRPORT}` not found among "
            f"{len(raw['airports'])} airports"
        )
    else:
        missing_fields = [f for f in AIRPORT_REQUIRED_FIELDS if f not in dub]
        if missing_fields:
            failures.append(
                f"aggregate: airport `{SAMPLE_AIRPORT}` is missing fields "
                f"`{missing_fields}` (got `{sorted(dub.keys())}`)"
            )
        coords = dub.get("coordinates")
        if isinstance(coords, dict):
            missing_coords = [k for k in ("latitude", "longitude") if k not in coords]
            if missing_coords:
                failures.append(
                    f"aggregate: airport `{SAMPLE_AIRPORT}` coordinates missing "
                    f"`{missing_coords}` (got `{sorted(coords.keys())}`)"
                )

    if not failures:
        try:
            network = parse_network(raw)
        except Exception as exc:  # noqa: BLE001 - report any parse drift
            failures.append(f"aggregate: `parse_network` raised `{exc!r}`")
        else:
            if not network.airports or not network.countries:
                failures.append(
                    "aggregate: parsed network is unexpectedly sparse "
                    f"({len(network.airports)} airports, "
                    f"{len(network.countries)} countries)"
                )
    return failures


def _fetch_fares(transport: RyanairTransport, days: int) -> Dict[str, Any]:
    # FlightSearchParams validates against naive datetime.now(); stay naive.
    start = datetime.now() + timedelta(days=FARE_DAYS_AHEAD)
    params = FlightSearchParams(
        from_airport=FARE_ORIGIN,
        to_airport=FARE_DESTINATION,
        from_date=start,
        to_date=start + timedelta(days=days - 1),
    )
    return transport.get_json(ONE_WAY_FARES_URL, serialize_search_params(params))


def check_fare_search(transport: RyanairTransport) -> List[str]:
    """Verify a DUB->BCN fare search still parses with ``parse_flight``."""
    raw = _fetch_fares(transport, days=1)

    if not isinstance(raw, dict) or "fares" not in raw:
        got = sorted(raw.keys()) if isinstance(raw, dict) else type(raw).__name__
        return [f"oneWayFares: missing top-level `fares` key (got `{got}`)"]

    fares = raw["fares"]
    if not fares:
        # No DUB->BCN flight on that single day would be unusual but not
        # impossible; only alarm if a week-wide window is also empty.
        raw = _fetch_fares(transport, days=7)
        fares = raw.get("fares", [])
        if not fares:
            return [
                f"oneWayFares: 0 fares for {FARE_ORIGIN}->{FARE_DESTINATION} across "
                f"a 7-day window {FARE_DAYS_AHEAD} days out — route gone or "
                "params silently rejected"
            ]

    failures: List[str] = []
    for i, fare in enumerate(fares):
        if "outbound" not in fare:
            failures.append(
                f"oneWayFares: fare[{i}] missing `outbound` (got `{sorted(fare.keys())}`)"
            )
            continue
        try:
            parse_flight(fare["outbound"])
        except Exception as exc:  # noqa: BLE001 - report any parse drift
            failures.append(
                f"oneWayFares: `parse_flight` raised `{exc!r}` on fare[{i}] "
                f"(outbound keys: `{sorted(fare['outbound'].keys())}`)"
            )
            break
    return failures


def run_checks() -> List[str]:
    failures: List[str] = []
    transport = RyanairTransport()
    try:
        for name, check in (
            ("aggregate", check_aggregate),
            ("fare search", check_fare_search),
        ):
            try:
                failures.extend(check(transport))
            except Exception as exc:  # noqa: BLE001 - a dead endpoint is a finding
                failures.append(
                    f"{name}: probe crashed with `{exc!r}`\n"
                    f"```\n{traceback.format_exc()}```"
                )
    finally:
        transport.close()
    return failures


def write_report(path: str, failures: List[str]) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    lines = [
        "## Live API health check failed",
        "",
        f"Probed the live Ryanair API on {today} (UTC); "
        f"{len(failures)} check(s) no longer hold:",
        "",
        *(f"- {f}" for f in failures),
        "",
        "If the upstream shape changed, update `flyan/wire.py` and "
        "`docs/internal-api-spec.md` to match.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default=None,
        help="write a markdown failure report to this path (only on failure)",
    )
    args = parser.parse_args()

    failures = run_checks()
    if not failures:
        print("Live API health check passed.")
        return 0

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if args.report:
        write_report(args.report, failures)
    return 1


if __name__ == "__main__":
    sys.exit(main())
