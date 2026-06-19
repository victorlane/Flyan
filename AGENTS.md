# AGENTS.md

Notes for AI agents working in this repo. The file follows the
[agents.md](https://agents.md) convention so Claude Code, Cursor, Aider,
and similar tools pick it up automatically.

## What Flyan is

An unofficial Python SDK for Ryanair's undocumented public flight-search
API, plus an optional MCP server that exposes the same surface to LLM
agents in natural language.

There is no API contract from Ryanair. Behaviour is reverse-engineered from
poking the live endpoints; the source of truth for endpoint quirks is
`docs/internal-api-spec.md`. Update that doc whenever an endpoint's
behaviour, params, or response shape changes.

## Layout

```
flyan/
  ryanair.py        # Sync client (RyanAir). Domain-friendly methods that
                    # build URLs, delegate to transport, and call parsers.
  async_client.py   # Async mirror (AsyncRyanAir). Keep in lockstep with
                    # ryanair.py — every public method on one should exist
                    # on the other with the same signature.
  transport.py      # HTTP seam. Owns httpx, retries, UA rotation, cookie
                    # warm-up, Accept-Encoding, and nextPage pagination.
                    # Adapters: RyanairTransport, AsyncRyanairTransport,
                    # CachingTransport.
  wire.py           # Translation between public models and Ryanair wire
                    # format. Field-name quirks (departureAirportIataCode,
                    # lowercase iso2, currency-as-query-param) live HERE
                    # and nowhere else.
  misc.py           # Public Pydantic models (Flight, FlightSearchParams,
                    # Network, NetworkAirport, DestinationFare, ...).
                    # No wire knowledge.
  tracker.py        # Local PriceTracker for price-history analysis.
  mcp_server.py     # FastMCP server exposing curated tools to agents.
  currencies.json   # Static lookup of supported ISO 4217 currencies.

docs/
  internal-api-spec.md  # Living notes on the undocumented Ryanair API.
                        # READ THIS before adding or modifying an endpoint.
```

## Architectural seams

The codebase splits along three seams and the split is load-bearing. Do
not collapse them.

1. **transport** — knows HTTP, retries, cookies, pagination. Returns
   parsed JSON. Knows nothing about flights.
2. **wire** — knows Ryanair's field names and quirks. Translates between
   `misc` models and wire dicts.
3. **coordinator** (`ryanair.py` / `async_client.py`) — exposes
   domain-friendly methods. Each one is a few lines: build URL + params,
   call transport, call parser.

If you find yourself putting wire-format strings in `ryanair.py` or HTTP
concerns in `wire.py`, you're working against the structure.

## Conventions

### Sync and async parity
Every public method on `RyanAir` has an equivalent on `AsyncRyanAir`.
Add to both, or neither. The async one is not an afterthought.

### Error contract
Public methods return `[]` only when the API answered with no matching
results. Anything else — network failure, status error, decode error,
schema mismatch — raises `RyanairException`. Callers that need to
distinguish transient from permanent failures inspect the exception chain.

### Country codes are lowercase ISO2
Uppercase silently returns zero fares from the API. `wire.py` lowercases
on serialization. Don't undo that.

### Dates are `datetime`, not `date`, in the public API
The wire layer reduces to ISO dates where needed. Callers pass datetimes.

### Pydantic models, not dataclasses
Validation lives on the model. New public structures should be
`BaseModel` subclasses in `misc.py`.

### No comments that explain *what*
Self-documenting code, plus one-line *why* comments only when the
constraint is non-obvious (a hidden API quirk, a workaround for a
specific bug). Don't write multi-line docstrings inside private helpers.

### Avoid em dashes in user-facing prose
README, release notes, and AGENTS.md use commas, periods, or colons
instead. (Code comments are fine.)

## When you add an endpoint

1. Check `docs/internal-api-spec.md` first. If the endpoint is documented
   there, use the documented field names and quirks.
2. Verify the live shape with a quick probe before writing the parser —
   the API has changed shape under us before.
3. Add the wire translation to `wire.py`. Field-name quirks belong here.
4. Add the public method to `ryanair.py` AND `async_client.py`.
5. If the response is a new domain object, add the model to `misc.py` and
   export it from `flyan/__init__.py`.
6. Update `docs/internal-api-spec.md` so future-you doesn't have to
   reverse-engineer it again.
7. Consider whether the new endpoint deserves an MCP tool in
   `flyan/mcp_server.py` (rule of thumb: yes if it answers a
   natural-language question, no if it's a low-level building block).

## Testing

There is no test suite at the moment. Smoke-test changes against the
live API:

```bash
.venv/bin/python -c "from flyan import RyanAir; ..."
```

The API is anonymous, so this is cheap. Wrap the transport in
`CachingTransport` when iterating on aggregate-endpoint work so you
don't refetch the network metadata on every run.

## Release flow

Releases are automated:

1. Land conventional commits to `master` (`feat:`, `fix:`, `docs:`, etc.).
2. The `release-please` workflow opens a release PR.
3. Merge the release PR.
4. Tag is pushed automatically (currently re-push manually if it doesn't
   trigger the PyPI publish — see open issue about `GITHUB_TOKEN`
   limitations).
5. `release.yml` builds and publishes to PyPI on the tag.

`CHANGELOG.md` is gitignored. The canonical changelog is the GitHub
Releases page, which release-please populates.

Version is tracked in three places that must stay in sync:
`pyproject.toml`, `.release-please-manifest.json`, `flyan/__init__.py`.

## Commit messages

- Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`,
  `refactor:`, `test:`). `release-please` keys off these.
- **Do not add `Co-Authored-By:` trailers for AI assistants** (Claude,
  Copilot, Cursor, etc.). Commits are authored by the human running the
  tool. No "Generated with" footers either.
- Keep the subject under 72 chars and write it in the imperative
  ("add X", not "added X").

## What not to do

- Don't import directly from `httpx` outside `transport.py`. Anywhere else
  should accept a `Transport` / `AsyncTransport`.
- Don't add fallbacks for "what if Ryanair changes the field name". They
  haven't, and if they do we want to fail loudly so we update the parser.
- Don't add retry logic outside `transport.py`. There's already
  exponential backoff there; double-retrying just hides bugs.
- Don't commit `currencies.json` re-orderings without a behaviour change.
  The file gets re-sorted by some tools; ignore that noise.
- Don't add a CHANGELOG.md by hand. It's gitignored on purpose.
