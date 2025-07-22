import logging
from datetime import datetime
from typing import Dict, Any

import httpx
from fake_useragent.fake import UserAgent
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from flyan.misc import (
    Airport,
    Flight,
    FlightSearchParams,
    ReturnFlight,
    currencies,
)

ua = UserAgent()
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


class RyanAir:
    """
    Create a RyanAir instance

    :param str currency: Preferred currency
    """

    BASE_SERVICES_API_URL = "https://services-api.ryanair.com/farfnd/v4"
    AGGREGATE_URL = "https://www.ryanair.com/api/views/locate/3/aggregate/all/en"

    def __init__(self, currency: str = "EUR"):
        self.client = httpx.Client(
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "en-GB,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Priority": "u=0, i",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": ua.random,
            },
            follow_redirects=True,
        )

        self.__get("https://www.ryanair.com")

        if currency in currencies.keys():
            self.currency = currency

        else:
            self.currency = "EUR"

    def __del__(self):
        self.client.close()

    @retry(
        stop=stop_after_attempt(5),  # Retry up to 5 times
        wait=wait_exponential(),
        retry=retry_if_exception_type(Exception),
        reraise=True,  # Raise the exception after retries are exhausted
    )
    def __get(self, url: str, params: dict[str, str] = {}) -> httpx.Response:
        """
        Send a GET request to url

        :param str url: The url to GET
        :param dict params: URL Parameters for the query
        :return httpx.Response: Response object
        :raises httpx.HTTPStatusError: If one occurred
        """
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return response

    def __parse_airport(self, airport: Dict[str, Any]) -> Airport:
        return Airport(
            country_name=airport["countryName"],
            iata_code=airport["iataCode"],
            name=airport["name"],
            seo_name=airport["seoName"],
            city_name=airport["city"]["name"],
            city_code=airport["city"]["code"],
            city_country_code=airport["city"]["countryCode"],
        )

    def __parse_fare(self, fare: Dict[str, Any], k: str = "outbound") -> Flight:
        dep_date = datetime.fromisoformat(fare[k]["departureDate"])
        arr_date = datetime.fromisoformat(fare[k]["arrivalDate"])

        return Flight(
            departure_airport=self.__parse_airport(fare[k]["departureAirport"]),
            arrival_airport=self.__parse_airport(fare[k]["arrivalAirport"]),
            departure_date=dep_date,
            arrival_date=arr_date,
            price=fare[k]["price"]["value"],
            currency=fare[k]["price"]["currencyCode"],
            flight_key=fare[k]["flightKey"],
            flight_number=fare[k]["flightNumber"],
            previous_price=fare[k].get("previousPrice", None),
        )

    def __parse_return_fare(self, fare: Dict[str, Any]) -> ReturnFlight:
        outbound = self.__parse_fare(fare, "outbound")
        inbound = self.__parse_fare(fare, "inbound")

        return ReturnFlight(
            outbound=outbound,
            inbound=inbound,
            summary_price=fare["summary"]["price"]["value"],
            summary_currency=fare["summary"]["price"]["currencyCode"],
            previous_price=fare.get("previousPrice") or 0,
        )

    def get_oneways(self, params: FlightSearchParams) -> list[Flight]:
        """
        Get oneways
        """
        print("Getting oneways")
        url = f"{self.BASE_SERVICES_API_URL}/oneWayFares"

        try:
            r = self.__get(url, params.to_api_params())
            if not r.is_success:
                return []

            fares = r.json()["fares"]
            flights = [self.__parse_fare(f) for f in fares]

            return flights

        except httpx.HTTPError:
            logger.error(f"A HTTP Error occured trying to get {url}", exc_info=True)
            return []

        except KeyError as KE:
            print(KE)
            return []
