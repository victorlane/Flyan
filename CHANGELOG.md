# Changelog

## [0.1.1](https://github.com/victorlane/Flyan/compare/v0.1.0...v0.1.1) (2026-06-12)


### Documentation

* **readme:** document explore mode endpoints ([7ffa2ce](https://github.com/victorlane/Flyan/commit/7ffa2ce9f4f43314e5e032cb4506d4083f6a67fc))

## 0.1.0 (2026-06-12)


### ⚠ BREAKING CHANGES

* **client:** FlightSearchParams.to_api_params() no longer exists; callers building wire dicts directly should call flyan.wire.serialize_search_params(params, currency=...). The bundled stations.json is also gone — code that imported it through flyan.misc.stations will need to call RyanAir.get_network() instead.
* **client:** FlightSearchParams.to_api_params() now takes a keyword-only currency argument. External callers passing params directly to the API will need to update.

### Features

* **client:** add explore mode for destination discovery ([77b8f57](https://github.com/victorlane/Flyan/commit/77b8f57daa18ad5a0b2f31138b7ece7963227490))
* **client:** add new endpoints, search helpers, and async client ([4c0d38c](https://github.com/victorlane/Flyan/commit/4c0d38c879daa1dc0c5cebda638f8e2d8f944ea5))
* **client:** add return fares, daily fares, schedules, network endpoints ([d45ee60](https://github.com/victorlane/Flyan/commit/d45ee608d6866b9aa4b0e1dbe0723924cbeca1c5))
* **models:** add typed Route union and ReturnDailyFares ([e4ad841](https://github.com/victorlane/Flyan/commit/e4ad841b81f4a96ef6ad6387b96711b49be4ed19))
* **tracker:** add local PriceTracker for price-history analysis ([8f7f925](https://github.com/victorlane/Flyan/commit/8f7f92596b6741bb9e5bbf53228aa55fae0bc3ac))
* **transport:** add async transport and TTL CachingTransport ([26abdba](https://github.com/victorlane/Flyan/commit/26abdba4c64ed6f32a4d794a681834d5d7109713))


### Documentation

* add internal API spec for undocumented Ryanair endpoints ([09daee6](https://github.com/victorlane/Flyan/commit/09daee61fbd6ad75d64292f52a73ce6b858306e1))


### Code Refactoring

* **client:** split client into transport, wire, and coordinator seams ([7391e5d](https://github.com/victorlane/Flyan/commit/7391e5db8cd48d59eb411c0f9edae453792e81c5))
