# Flyan SDK

[![PyPI version](https://img.shields.io/pypi/v/Flyan.svg)](https://pypi.org/project/Flyan/)
[![Python versions](https://img.shields.io/pypi/pyversions/Flyan.svg)](https://pypi.org/project/Flyan/)
[![CI](https://github.com/victorlane/Flyan/actions/workflows/ci.yml/badge.svg)](https://github.com/victorlane/Flyan/actions/workflows/ci.yml)
[![CodeQL](https://github.com/victorlane/Flyan/actions/workflows/codeql.yml/badge.svg)](https://github.com/victorlane/Flyan/actions/workflows/codeql.yml)
[![PyPI downloads](https://img.shields.io/pypi/dm/Flyan.svg)](https://pypi.org/project/Flyan/)
[![License](https://img.shields.io/github/license/victorlane/Flyan.svg)](https://github.com/victorlane/Flyan/blob/master/LICENSE)

An open-source unofficial API wrapper to get flight data from Ryanair.

> [!TIP]
> **New: MCP server for AI agents.** Plug Flyan into Claude Desktop,
> Claude Code, or Cursor and search Ryanair flights in natural language.
> Jump to the [MCP Quickstart](#use-with-claude-cursor-and-other-mcp-clients).

## Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Data Models](#data-models)
- [Examples](#examples)
- [Explore Mode](#explore-mode)
- [**Use with Claude, Cursor, and other MCP clients**](#use-with-claude-cursor-and-other-mcp-clients)
- [Supported Airports](#supported-airports)
- [Supported Currencies](#supported-currencies)
- [Rate Limiting](#rate-limiting)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)

## Installation

```bash
pip install Flyan
```

Or using uv:

```bash
uv add Flyan
```

## Quick Start

```python
from datetime import datetime
from flyan import RyanAir, FlightSearchParams

# Initialize the client
client = RyanAir(currency="EUR")

# Set up search parameters
search_params = FlightSearchParams(
    from_airport="DUB",  # Dublin
    to_airport="BCN",    # Barcelona
    from_date=datetime(2025, 8, 15),
    to_date=datetime(2025, 8, 20),
    max_price=200
)

# Search for one-way flights
flights = client.get_oneways(search_params)

# Display results
for flight in flights:
    print(f"Flight {flight.flight_number}: {flight.departure_airport.name} → {flight.arrival_airport.name}")
    print(f"Departure: {flight.departure_date}")
    print(f"Price: {flight.price} {flight.currency}")
    print("---")
```

## API Reference

### RyanAir Class

#### Constructor

```python
RyanAir(currency: str = "EUR")
```

Creates a new RyanAir client instance.

**Parameters:**

- `currency` (str, optional): Preferred currency for pricing. Defaults to "EUR". Must be a valid currency code from the supported currencies list.

**Example:**

```python
# Default EUR currency
client = RyanAir()

# Specific currency
client = RyanAir(currency="USD")
```

#### Methods

##### `get_oneways(params: FlightSearchParams) -> list[Flight]`

Search for one-way flights.

**Parameters:**

- `params` (FlightSearchParams): Search parameters

**Returns:**

- `list[Flight]`: List of available flights

### FlightSearchParams Class

Parameters for searching flights.

```python
FlightSearchParams(
    from_airport: str,
    from_date: datetime,
    to_date: datetime,
    destination_country: Optional[str] = None,
    max_price: Optional[int] = None,
    to_airport: Optional[str] = None,
    departure_time_from: Optional[str] = "00:00",
    departure_time_to: Optional[str] = "23:59"
)
```

**Parameters:**

- `from_airport` (str): IATA code of departure airport (e.g., "DUB")
- `from_date` (datetime): Earliest departure date
- `to_date` (datetime): Latest departure date
- `destination_country` (str, optional): Country code for destination
- `max_price` (int, optional): Maximum price filter
- `to_airport` (str, optional): IATA code of arrival airport
- `departure_time_from` (str, optional): Earliest departure time (HH:MM format)
- `departure_time_to` (str, optional): Latest departure time (HH:MM format)

**Example:**

```python
from datetime import datetime

params = FlightSearchParams(
    from_airport="DUB",
    from_date=datetime(2025, 8, 15),
    to_date=datetime(2025, 8, 20),
    to_airport="BCN",
    max_price=150,
    departure_time_from="08:00",
    departure_time_to="18:00"
)
```

### ReturnFlightSearchParams Class

Extended parameters for return flight searches.

```python
ReturnFlightSearchParams(
    # All FlightSearchParams fields plus:
    return_date_from: datetime,
    return_date_to: datetime,
    inbound_departure_time_from: Optional[str] = "00:00",
    inbound_departure_time_to: Optional[str] = "23:59"
)
```

## Data Models

### Flight

Represents a single flight.

**Attributes:**

- `departure_airport` (Airport): Departure airport information
- `arrival_airport` (Airport): Arrival airport information
- `departure_date` (datetime): Departure date and time
- `arrival_date` (datetime): Arrival date and time
- `price` (float): Flight price
- `currency` (str): Price currency
- `flight_key` (str): Unique flight identifier
- `flight_number` (str): Flight number
- `previous_price` (Optional[str | float]): Previous price if available

### Airport

Represents airport information.

**Attributes:**

- `country_name` (str): Country name
- `iata_code` (str): IATA airport code
- `name` (str): Airport name
- `seo_name` (str): SEO-friendly name
- `city_name` (str): City name
- `city_code` (str): City code
- `city_country_code` (str): Country code

### ReturnFlight

Represents a return flight booking.

**Attributes:**

- `outbound` (Flight): Outbound flight
- `inbound` (Flight): Return flight
- `summary_price` (float): Total price for both flights
- `summary_currency` (str): Currency for total price
- `previous_price` (str | float): Previous total price if available

### NetworkAirport

Represents an airport in Ryanair's live network. Returned by the explore methods.

**Attributes:**

- `iata_code` (str): IATA airport code
- `name` (str): Airport name
- `seo_name` (str): SEO-friendly name
- `country_code` (str): Lowercase ISO2 country code (e.g. "ie", "es")
- `city_code` (str): City code (e.g. "LONDON", "DUBLIN")
- `region_code` (Optional[str]): Region code (e.g. "SCOTLAND", "ANDALUSIA")
- `currency_code` (str): Local currency code
- `time_zone` (str): IANA timezone (e.g. "Europe/Dublin")
- `base` (bool): True if this is a Ryanair base
- `latitude` (float), `longitude` (float): Coordinates
- `routes` (list[str]): Raw route strings (year-round)
- `seasonal_routes` (list[str]): Raw route strings (seasonal-only)
- `categories` (list[str]): Marketing categories assigned by Ryanair
- `aliases` (list[str]): Alternative names

Helpers: `airport_routes()`, `country_routes()`, `seasonal_airport_routes()`,
`typed_routes()`, `typed_seasonal_routes()`.

### DestinationFare

Returned by `explore_with_fares()`. Pairs a reachable destination with its
cheapest sampled fare, if one was returned by the price probe.

**Attributes:**

- `airport` (NetworkAirport): The destination airport
- `fare` (Optional[Flight]): The cheapest sampled fare in the window, or `None`
  if the route is in the network but no priced inventory came back (no flights
  in the window, sold out, etc.)

## Examples

### Search by Country

```python
# Search flights to any airport in Spain
params = FlightSearchParams(
    from_airport="DUB",
    destination_country="ES",
    from_date=datetime(2025, 9, 1),
    to_date=datetime(2025, 9, 7)
)

flights = client.get_oneways(params)
```

### Filter by Time and Price

```python
# Morning flights under €100
params = FlightSearchParams(
    from_airport="STN",  # London Stansted
    to_airport="DUB",    # Dublin
    from_date=datetime(2025, 8, 1),
    to_date=datetime(2025, 8, 5),
    max_price=100,
    departure_time_from="06:00",
    departure_time_to="12:00"
)

flights = client.get_oneways(params)
```

### Error Handling

```python
from flyan import RyanairException

try:
    flights = client.get_oneways(params)
    if not flights:
        print("No flights found for the given criteria")
except RyanairException as e:
    print(f"Ryanair API error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Explore Mode

Explore Mode answers the question "where can I actually fly from here?". It
reads Ryanair's live network metadata once and exposes the reachable
destinations from any airport, optionally grouped, filtered, or joined with
the cheapest fare in a date window.

All methods below are available on both `RyanAir` and `AsyncRyanAir`.

### List every destination

```python
destinations = client.get_destinations("DUB")

for airport in destinations:
    print(f"{airport.iata_code} {airport.name} ({airport.country_code})")
```

### Filter by country, region or city

```python
# All Scottish airports DUB flies to
in_scotland = client.get_destinations_in_region("DUB", "SCOTLAND")

# All London airports DUB flies to (LGW, LTN, STN)
in_london = client.get_destinations_in_city("DUB", "LONDON")

# All Spanish airports DUB flies to
in_spain = client.get_destinations_in_country("DUB", "es")
```

Country codes are lowercase ISO2. Region and city codes come from the live
network (uppercase, e.g. `SCOTLAND`, `ANDALUSIA`, `COSTA_DE_SOL`, `LONDON`,
`MILAN`).

### Group destinations

```python
# {country_code: [airports]}
by_country = client.explore_by_country("DUB")

print(f"DUB flies to {len(by_country)} countries")
for country, airports in sorted(by_country.items()):
    codes = ", ".join(a.iata_code for a in airports)
    print(f"  {country}: {codes}")
```

```python
# {region_code: [airports]}
by_region = client.explore_by_region("DUB")
```

Airports without a `region_code` are collected under the empty-string key,
so callers can decide whether to surface or drop them.

### Seasonal-only destinations

```python
seasonal = client.get_seasonal_destinations("DUB")
```

Ryanair's `seasonalRoutes` list is sparsely populated upstream, so this often
returns `[]` outside of summer/winter schedule transitions. The method is
provided so callers do not need to peek at the raw route strings.

### Destinations with their cheapest fare

`explore_with_fares()` joins the network destinations with a `oneWayFares`
probe, so each destination comes back with its cheapest sampled `Flight` (or
`None` if no fare was returned for that route in the window). It costs one
network call plus one fare call.

```python
from datetime import datetime, timedelta

start = datetime.now() + timedelta(days=14)
end = start + timedelta(days=7)

results = client.explore_with_fares("DUB", start, end, max_price=100)

priced = [d for d in results if d.fare is not None]
cheapest_first = sorted(priced, key=lambda d: d.fare.price)

for d in cheapest_first[:10]:
    print(f"{d.airport.iata_code} {d.airport.name}: "
          f"{d.fare.price} {d.fare.currency}")
```

### Async usage

`AsyncRyanAir` mirrors every explore method:

```python
import asyncio
from flyan import AsyncRyanAir

async def main():
    async with AsyncRyanAir() as client:
        by_country = await client.explore_by_country("DUB")
        print(f"{len(by_country)} countries reachable from DUB")

asyncio.run(main())
```

If you call multiple explore methods in a row, wrap the transport in
`CachingTransport` so the network metadata is fetched once and reused.

## Use with Claude, Cursor, and other MCP clients

> [!IMPORTANT]
> Two commands and you're done:
>
> ```bash
> uv tool install "Flyan[mcp]"
> claude mcp add flyan flyan-mcp
> ```
>
> Now your agent can search Ryanair flights in natural language. No API
> keys, no accounts.

Flyan ships an optional Model Context Protocol server so your agent can
search Ryanair fares from natural-language prompts like *"find me a cheap
flight from Dublin to Spain in August under €150"* or *"what's the cheapest
day in July to fly DUB to BCN"*.

### Quickstart

**1. Install Flyan with the MCP extra:**

```bash
uv tool install "Flyan[mcp]"
```

Or with pip:

```bash
pipx install "Flyan[mcp]"
```

This installs a `flyan-mcp` console script on your PATH.

**2. Add it to your agent:**

**Claude Code** (one-liner):

```bash
claude mcp add flyan flyan-mcp
```

**Claude Desktop**: open `~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS (or `%APPDATA%\Claude\claude_desktop_config.json` on Windows) and add:

```json
{
  "mcpServers": {
    "flyan": {
      "command": "flyan-mcp"
    }
  }
}
```

Then restart Claude Desktop.

**Cursor**: Settings → MCP → Add new server, name `flyan`, command `flyan-mcp`.

**3. Try it.** Ask your agent:

> "Find me a one-way from Dublin to anywhere in Spain in the first week of
> August under €150."

The agent should call `find_flights` with `destination_country="es"`, then
summarize the cheapest options.

### Exposed tools

The server exposes four curated tools so the agent can pick reliably:

- `find_flights` for one-way searches with optional country, IATA, or price filters
- `find_anywhere_under` for "where can I go for under £X" prompts
- `explore_destinations` for "what countries can I reach from X"
- `cheapest_per_day` for "what's the cheapest day this month to fly X to Y"

No API keys, accounts, or rate-limit setup. Ryanair's API is anonymous and
the server reuses a single `RyanAir` client across calls.

## Supported Airports

The SDK supports all airports in Ryanair's network. Airport codes must be valid 3-letter IATA codes. The live list is fetched from Ryanair's aggregate endpoint via `client.get_network()`; iterate `network.airports` for the full set.

Popular airports include:

- **DUB** - Dublin
- **STN** - London Stansted
- **BCN** - Barcelona
- **MAD** - Madrid
- **FCO** - Rome Fiumicino
- **BRU** - Brussels
- **AMS** - Amsterdam

## Supported Currencies

The SDK supports multiple currencies. Some popular ones include:

- **EUR** - Euro
- **USD** - US Dollar
- **GBP** - British Pound
- **CHF** - Swiss Franc

See `currencies.json` for the complete list.

## Rate Limiting

The SDK includes automatic retry logic with exponential backoff to handle rate limiting and temporary API issues. It will retry failed requests up to 5 times before giving up.

## Contributing

This is an open-source project. Contributions are welcome!

## Disclaimer

This is an unofficial API wrapper and is not affiliated with Ryanair. Use at your own risk and ensure you comply with Ryanair's terms of service.
