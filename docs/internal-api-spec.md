# Ryanair Internal API Spec

Living notes on the undocumented Ryanair endpoints Flyan talks to (or could talk to).
Reverse-engineered from poking the live API on 2026-06-11. Update whenever an
endpoint's behaviour, params, or response shape changes.

All endpoints respond JSON. All require the client to first hit
`https://www.ryanair.com` once so the session/cookies are set; calling the
services-api host cold sometimes 403s.

A realistic browser `User-Agent` is recommended. The Flyan client rotates one via
`fake-useragent`.

---

## Hosts

| Host | Purpose |
|---|---|
| `services-api.ryanair.com` | Fare search, schedules. The main "read" surface. |
| `www.ryanair.com/api/views/locate/3` | Static network metadata (airports, cities, countries). |
| `www.ryanair.com/api/booking/v4` | Booking flow (availability, pricing, seat map). Requires a live session. |

---

## `GET /farfnd/v4/oneWayFares`

Cheapest one-way fares in a date window.

**Query params**

| Name | Required | Notes |
|---|---|---|
| `departureAirportIataCode` | yes | Uppercase IATA, e.g. `DUB`. |
| `outboundDepartureDateFrom` | yes | ISO date, e.g. `2026-07-01`. |
| `outboundDepartureDateTo` | yes | ISO date. |
| `outboundDepartureTimeFrom` | yes | `HH:MM`, default `00:00`. |
| `outboundDepartureTimeTo` | yes | `HH:MM`, default `23:59`. |
| `arrivalAirportIataCode` | no | Uppercase IATA. Omit for "anywhere". |
| `arrivalCountryCode` | no | **lowercase ISO2**, e.g. `es`, `gb`. Uppercase returns 0 fares silently. |
| `priceValueTo` | no | Max price, integer. |
| `currency` | no | ISO 4217, e.g. `EUR`, `USD`, `GBP`. Server returns prices in this currency. If omitted defaults to the departure airport's local currency (DUB→EUR, STN→GBP). |
| `market` | no | Locale, e.g. `en-gb`. Doesn't affect fares but tweaks display fields. |
| `limit` | no | Page size. Server default is large enough to fit a full month from one origin (~120 fares). |
| `offset` | no | Page offset. Pair with `nextPage` from response. |

**Response shape**

```json
{
  "arrivalAirportCategories": null,
  "fares": [ /* Fare[] */ ],
  "nextPage": null,
  "size": 119
}
```

`Fare` (one-way):

```json
{
  "outbound": {
    "departureAirport": { /* Airport */ },
    "arrivalAirport":   { /* Airport */ },
    "departureDate": "2026-07-02T21:50:00",
    "arrivalDate":   "2026-07-03T01:20:00",
    "price": {
      "value": 82.31,
      "valueMainUnit": "82",
      "valueFractionalUnit": "31",
      "currencyCode": "EUR",
      "currencySymbol": "€"
    },
    "flightKey": "FR~6395~ ~~DUB~07/02/2026 21:50~BCN~07/03/2026 01:20~ ~ ",
    "flightNumber": "FR6395",
    "previousPrice": null,
    "priceUpdated": 1749594000000
  }
}
```

`Airport`:

```json
{
  "countryName": "Ireland",
  "iataCode": "DUB",
  "name": "Dublin",
  "seoName": "dublin",
  "city": {
    "name": "Dublin",
    "code": "DUBLIN",
    "countryCode": "ie",
    "macCode": null
  }
}
```

`priceUpdated` is epoch-ms. Not currently parsed by Flyan.

---

## `GET /farfnd/v4/roundTripFares`

Cheapest return fares in two date windows. Same query params as `oneWayFares`
plus the inbound window:

| Name | Required | Notes |
|---|---|---|
| `inboundDepartureDateFrom` | yes | ISO date. |
| `inboundDepartureDateTo` | yes | ISO date. |
| `inboundDepartureTimeFrom` | yes | `HH:MM`. |
| `inboundDepartureTimeTo` | yes | `HH:MM`. |

`Fare` (return):

```json
{
  "outbound": { /* same as one-way Fare.outbound */ },
  "inbound":  { /* same shape */ },
  "summary": {
    "price": { /* Price */ },
    "previousPrice": null,
    "newRoute": false,
    "tripDurationDays": 9
  }
}
```

**Flyan gap**: types exist (`ReturnFlight`, `ReturnFlightSearchParams`) and
`__parse_return_fare` is implemented, but no public `get_returns()` method
exposes this. Easy win.

---

## `GET /farfnd/v4/oneWayFares/{origin}/{dest}/cheapestPerDay`

Daily cheapest fare for one route across one month. Powers the booking
calendar.

**Path params**: `origin`, `dest` — uppercase IATAs.

**Query params**

| Name | Required | Notes |
|---|---|---|
| `outboundMonthOfDate` | yes | First-of-month, ISO date, e.g. `2026-07-01`. |
| `currency` | no | Same as `oneWayFares`. |

**Response**

```json
{
  "outbound": {
    "fares": [
      {
        "day": "2026-07-01",
        "departureDate": "2026-07-01T19:05:00",
        "arrivalDate":   "2026-07-01T22:35:00",
        "price": { /* Price, may be null if no flight that day */ },
        "soldOut": false,
        "unavailable": false
      }
    ]
  }
}
```

Useful for "where's the cheapest day this month" — much faster than scanning
`oneWayFares` day by day. **Not in Flyan.**

---

## `GET /timtbl/3/schedules/{origin}/{dest}/years/{year}/months/{month}`

Published timetable (no prices). Tells you which days a route runs and at what
time.

**Path params**: uppercase IATAs, four-digit year, non-padded month.

**Response**

```json
{
  "month": 7,
  "days": [
    {
      "day": 1,
      "flights": [
        {
          "carrierCode": "FR",
          "number": "3977",
          "departureTime": "08:00",
          "arrivalTime": "11:30"
        }
      ]
    }
  ]
}
```

Days with no flights are simply absent from `days`. **Not in Flyan.**

---

## `GET /api/views/locate/3/aggregate/all/en`

The full network metadata bundle. Source of truth for routes, country codes,
currencies, time zones.

**No query params.**

**Response top-level keys**

- `airports` — 224 entries. Each has `iataCode`, `name`, `seoName`, `aliases`,
  `coordinates {latitude, longitude}`, `base` (bool), `countryCode` (lowercase
  iso2), `regionCode`, `cityCode`, `currencyCode`, `routes` (list of
  `airport:XXX` / `city:NAME` / `country:xx` / `region:NAME` strings),
  `seasonalRoutes`, `categories`, `priority`, `timeZone`.
- `cities` — 212 entries. `name`, `code`, `countryCode`, optional `macCode`.
- `regions` — 19 entries. `name`, `code`, `cites` (typo in upstream), each
  with `name`, `code`, optional `macCode`, `countryCode`.
- `countries` — 36 entries. `code` (lowercase iso2), `iso3code`, `name`,
  `currency`, `defaultAirportCode`, `schengen` (bool).

Flyan calls this lazily from `get_network()` and exposes it via:

- `validate_route()` — does origin fly to destination at all?
- `get_destinations()` / `get_destinations_in_country()` /
  `get_destinations_in_region()` / `get_destinations_in_city()` — reachable
  airports from an origin, optionally filtered.
- `get_seasonal_destinations()` — airports only reachable on a seasonal
  schedule (sparse upstream, often `[]`).
- `explore_by_country()` / `explore_by_region()` — same destinations grouped
  by ISO2 country or region code.
- `explore_with_fares()` — joins destinations with a `oneWayFares` probe so
  each destination carries its cheapest fare in the window (or `None`).

---

## Behavioural quirks worth remembering

- **Country codes are lowercase iso2.** Uppercase silently returns 0 fares.
  Flyan currently passes whatever the caller gives it — the README example
  uses `"ES"`, which never returns anything.
- **`currency` is a query param, not session state.** The `RyanAir(currency=...)`
  constructor stores the choice but never sends it; every result comes back in
  the departure airport's local currency.
- **`fake-useragent` triggers a network call to fetch the UA database at
  import time.** Slow start-up and breaks in air-gapped CI. A small bundled
  rotation list would be sufficient.
- **`__del__` closing the client is fragile.** If the interpreter is shutting
  down `httpx` may already be torn down — better to expose `close()` or
  implement `__enter__`/`__exit__`.
- **`outboundDepartureTimeFrom/To` are required for `oneWayFares`** even though
  they have sensible defaults. Flyan handles this correctly.
- **Date filter is a *departure window*, not a single date.** The window can
  be wide; the server returns the *cheapest* fare per route per day inside it.
  For a strict day, set `from == to`.
- **Pagination**: `nextPage` is non-null when results are truncated. Flyan does
  not follow it. For wide windows from a busy origin you may miss results.
- **Rate limiting**: aggressive retry with `wait_exponential()` and
  `retry_if_exception_type(Exception)` will mask programming errors as
  "transient" — narrow to `httpx.HTTPError` / 5xx and 429.
