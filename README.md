# Flyan SDK

An open-source unofficial API wrapper to get flight data from Ryanair.

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

## Supported Airports

The SDK supports all airports in Ryanair's network. Airport codes must be valid 3-letter IATA codes. You can find the complete list of supported airports in the `stations.json` file.

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
