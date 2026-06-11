import logging
import random
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from flyan.misc import (
    Airport,
    DailyFare,
    Flight,
    FlightSearchParams,
    Network,
    NetworkAirport,
    NetworkCountry,
    ReturnFlight,
    ReturnFlightSearchParams,
    TimetableFlight,
    currencies,
)

# Bundled UA rotation — avoids fake-useragent's network call on import,
# which breaks air-gapped CI and slows cold start.
_USER_AGENTS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)

logger = logging.getLogger("Flyan")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s:%(message)s", datefmt="%Y-%m-%d %I:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class RyanairException(Exception):
    def __init__(self, message: str):
        super().__init__(f"Ryanair API: {message}")


def _is_transient_http_error(exc: BaseException) -> bool:
    """Retry only on network/connection issues or 429/5xx — not on programming bugs."""
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return False


class RyanAir:
    """
    Create a RyanAir instance.

    :param currency: Preferred currency (ISO 4217). Sent to the API as a query
        param so prices come back in this currency regardless of the departure
        airport's locale.
    """

    BASE_SERVICES_API_URL = "https://services-api.ryanair.com/farfnd/v4"
    SCHEDULES_URL = "https://services-api.ryanair.com/timtbl/3/schedules"
    AGGREGATE_URL = "https://www.ryanair.com/api/views/locate/3/aggregate/all/en"
    HOMEPAGE_URL = "https://www.ryanair.com"

    def __init__(self, currency: str = "EUR"):
        self.client = httpx.Client(
            headers={
                "Accept": "application/json, text/plain, */*",
                # Only advertise encodings httpx can decode without extra deps.
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-GB,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "User-Agent": random.choice(_USER_AGENTS),
            },
            follow_redirects=True,
            timeout=30.0,
        )

        # services-api host often 403s if hit cold — warm cookies from the homepage.
        try:
            self._get(self.HOMEPAGE_URL)
        except httpx.HTTPError:
            logger.warning("Could not warm cookies from %s", self.HOMEPAGE_URL)

        self.currency = currency if currency in currencies else "EUR"

    # --- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client. Safe to call multiple times."""
        try:
            self.client.close()
        except Exception:
            pass

    def __enter__(self) -> "RyanAir":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- transport ---------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(),
        retry=retry_if_exception(_is_transient_http_error),
        reraise=True,
    )
    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        response = self.client.get(url, params=params or {})
        response.raise_for_status()
        return response

    # --- parsing -----------------------------------------------------------

    def _parse_airport(self, airport: Dict[str, Any]) -> Airport:
        return Airport(
            country_name=airport["countryName"],
            iata_code=airport["iataCode"],
            name=airport["name"],
            seo_name=airport["seoName"],
            city_name=airport["city"]["name"],
            city_code=airport["city"]["code"],
            city_country_code=airport["city"]["countryCode"],
        )

    def _parse_fare(self, fare: Dict[str, Any], k: str = "outbound") -> Flight:
        leg = fare[k]
        price_updated_ms = leg.get("priceUpdated")
        price_updated = (
            datetime.fromtimestamp(price_updated_ms / 1000)
            if isinstance(price_updated_ms, (int, float))
            else None
        )

        return Flight(
            departure_airport=self._parse_airport(leg["departureAirport"]),
            arrival_airport=self._parse_airport(leg["arrivalAirport"]),
            departure_date=datetime.fromisoformat(leg["departureDate"]),
            arrival_date=datetime.fromisoformat(leg["arrivalDate"]),
            price=leg["price"]["value"],
            currency=leg["price"]["currencyCode"],
            flight_key=leg["flightKey"],
            flight_number=leg["flightNumber"],
            previous_price=leg.get("previousPrice"),
            price_updated=price_updated,
        )

    def _parse_return_fare(self, fare: Dict[str, Any]) -> ReturnFlight:
        return ReturnFlight(
            outbound=self._parse_fare(fare, "outbound"),
            inbound=self._parse_fare(fare, "inbound"),
            summary_price=fare["summary"]["price"]["value"],
            summary_currency=fare["summary"]["price"]["currencyCode"],
            previous_price=fare["summary"].get("previousPrice") or 0,
        )

    # --- fare search -------------------------------------------------------

    def _fetch_fares(self, url: str, params: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Fetch all pages of a fares endpoint, following nextPage."""
        all_fares: list[Dict[str, Any]] = []
        next_params: Optional[Dict[str, Any]] = dict(params)
        # Hard cap to avoid runaway loops if the server keeps returning nextPage.
        for _ in range(20):
            if next_params is None:
                break
            r = self._get(url, next_params)
            if not r.is_success:
                break
            data = r.json()
            all_fares.extend(data.get("fares", []))
            next_page = data.get("nextPage")
            if not next_page:
                break
            # nextPage may be an absolute URL, a relative path, or an offset int.
            if isinstance(next_page, dict):
                next_params = {**params, **next_page}
            elif isinstance(next_page, int):
                next_params = {**params, "offset": next_page}
            else:
                break
        return all_fares

    def get_oneways(self, params: FlightSearchParams) -> list[Flight]:
        """Search for one-way fares."""
        url = f"{self.BASE_SERVICES_API_URL}/oneWayFares"
        try:
            fares = self._fetch_fares(url, params.to_api_params(currency=self.currency))
            return [self._parse_fare(f) for f in fares]
        except httpx.HTTPError:
            logger.exception("Failed to fetch one-way fares from %s", url)
            return []
        except (KeyError, ValueError):
            logger.exception("Unexpected response shape from %s", url)
            return []

    def get_returns(self, params: ReturnFlightSearchParams) -> list[ReturnFlight]:
        """Search for round-trip fares."""
        url = f"{self.BASE_SERVICES_API_URL}/roundTripFares"
        try:
            fares = self._fetch_fares(url, params.to_api_params(currency=self.currency))
            return [self._parse_return_fare(f) for f in fares]
        except httpx.HTTPError:
            logger.exception("Failed to fetch return fares from %s", url)
            return []
        except (KeyError, ValueError):
            logger.exception("Unexpected response shape from %s", url)
            return []

    def get_cheapest_per_day(
        self, origin: str, destination: str, month: datetime
    ) -> list[DailyFare]:
        """
        Daily cheapest fare for one route across one calendar month.

        :param origin: 3-letter IATA code.
        :param destination: 3-letter IATA code.
        :param month: Any datetime within the target month; only year+month are used.
        """
        url = (
            f"{self.BASE_SERVICES_API_URL}/oneWayFares/"
            f"{origin.upper()}/{destination.upper()}/cheapestPerDay"
        )
        params = {
            "outboundMonthOfDate": month.strftime("%Y-%m-01"),
            "currency": self.currency,
        }
        try:
            r = self._get(url, params)
            fares = r.json().get("outbound", {}).get("fares", [])
        except httpx.HTTPError:
            logger.exception("Failed to fetch cheapestPerDay from %s", url)
            return []
        except (KeyError, ValueError):
            logger.exception("Unexpected response shape from %s", url)
            return []

        result: list[DailyFare] = []
        for f in fares:
            price = f.get("price") or {}
            result.append(
                DailyFare(
                    day=datetime.fromisoformat(f["day"]),
                    departure_date=(
                        datetime.fromisoformat(f["departureDate"])
                        if f.get("departureDate")
                        else None
                    ),
                    arrival_date=(
                        datetime.fromisoformat(f["arrivalDate"])
                        if f.get("arrivalDate")
                        else None
                    ),
                    price=price.get("value"),
                    currency=price.get("currencyCode"),
                    sold_out=bool(f.get("soldOut")),
                    unavailable=bool(f.get("unavailable")),
                )
            )
        return result

    def get_schedule(
        self, origin: str, destination: str, year: int, month: int
    ) -> list[TimetableFlight]:
        """
        Published timetable for one route (no prices).

        Days with no service are omitted; each returned flight carries its
        scheduled departure and arrival times in local airport time.
        """
        url = (
            f"{self.SCHEDULES_URL}/"
            f"{origin.upper()}/{destination.upper()}/years/{year}/months/{month}"
        )
        try:
            r = self._get(url)
            data = r.json()
        except httpx.HTTPError:
            logger.exception("Failed to fetch schedules from %s", url)
            return []
        except (KeyError, ValueError):
            logger.exception("Unexpected response shape from %s", url)
            return []

        flights: list[TimetableFlight] = []
        for day in data.get("days", []):
            for f in day.get("flights", []):
                flights.append(
                    TimetableFlight(
                        carrier_code=f["carrierCode"],
                        flight_number=f["number"],
                        departure_time=f["departureTime"],
                        arrival_time=f["arrivalTime"],
                    )
                )
        return flights

    def get_network(self) -> Optional[Network]:
        """Fetch the live Ryanair network metadata (airports, countries, etc)."""
        try:
            r = self._get(self.AGGREGATE_URL)
            data = r.json()
        except httpx.HTTPError:
            logger.exception("Failed to fetch network from %s", self.AGGREGATE_URL)
            return None
        except (KeyError, ValueError):
            logger.exception(
                "Unexpected response shape from %s", self.AGGREGATE_URL
            )
            return None

        airports = [
            NetworkAirport(
                iata_code=a["iataCode"],
                name=a["name"],
                seo_name=a["seoName"],
                country_code=a["countryCode"],
                city_code=a["cityCode"],
                region_code=a.get("regionCode"),
                currency_code=a["currencyCode"],
                time_zone=a["timeZone"],
                base=bool(a.get("base", False)),
                latitude=a["coordinates"]["latitude"],
                longitude=a["coordinates"]["longitude"],
                routes=a.get("routes", []),
                seasonal_routes=a.get("seasonalRoutes", []),
                categories=a.get("categories", []),
                aliases=a.get("aliases", []),
                priority=a.get("priority"),
            )
            for a in data.get("airports", [])
        ]
        countries = [
            NetworkCountry(
                code=c["code"],
                iso3_code=c["iso3code"],
                name=c["name"],
                currency=c["currency"],
                default_airport_code=c.get("defaultAirportCode"),
                schengen=bool(c.get("schengen", False)),
            )
            for c in data.get("countries", [])
        ]
        return Network(
            airports=airports,
            countries=countries,
            cities=data.get("cities", []),
            regions=data.get("regions", []),
        )
