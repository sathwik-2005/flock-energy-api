# Flock Energy — Urja Meter Ops API

A clean, documented REST API wrapper around the legacy "Urja Meter Ops"
portal. It handles login/session management against the portal
automatically, normalises its HTML/JSON responses into consistent JSON,
and exposes a small set of documented endpoints so another engineer (or
program) never has to touch the original portal directly.

- **Source**: this repo (`app/`)
- **How the legacy portal actually works**: see [`PROTOCOL.md`](./PROTOCOL.md)
- **API spec**: see [`openapi.json`](./openapi.json), or run the server
  and browse `http://127.0.0.1:8000/docs` for interactive Swagger UI
- **Reflection**: see [`REFLECTION.md`](./REFLECTION.md)

## What's here

```
flock-energy-api/
├── app/
│   ├── main.py       # FastAPI routes
│   ├── client.py     # Adapter/scraper for the legacy portal - the only
│   │                 #   place that talks to Urja Meter Ops directly
│   ├── models.py     # Pydantic response schemas
│   └── config.py     # Env-driven settings (base URL, credentials, etc.)
├── PROTOCOL.md        # How the legacy portal works, as discovered
├── openapi.json        # OpenAPI 3.1 spec for THIS API (auto-generated
│                        #   from the running FastAPI app - not the
│                        #   portal's own, undocumented API)
├── REFLECTION.md
├── requirements.txt
├── .env.example
└── .gitignore
```

### Architecture, in one paragraph

`app/client.py` (`UrjaPortalClient`) is the only code that ever talks to
`urja-ops.flockenergy.tech`. It logs in with the given credentials,
holds the resulting session cookie in a persistent `httpx.Client`, and
transparently re-authenticates if a request comes back looking like the
session expired. `app/main.py` is a thin FastAPI layer on top of that
client — it never touches HTTP, cookies, or HTML itself, it just calls
`UrjaPortalClient` methods and returns Pydantic models. This separation
means the portal-specific messiness (HTML parsing, cookie handling, the
CSRF quirk described below) is contained in one file, and the API layer
stays boring and easy to read.

## Setup & running

Requires Python 3.10+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # defaults already match the given portal login
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/docs` for interactive Swagger UI, or
call the endpoints directly (see sample request below).

Config is entirely environment-driven (see `.env.example` /
`app/config.py`) — nothing is hardcoded except sensible defaults that
match the credentials given for this exercise.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/meters?q=&page=` | List/search meters. `q=""` returns the full, paginated list. |
| GET | `/api/v1/meters/{meter_id}` | Full detail: nameplate, network hierarchy, location, consumption. |
| GET | `/api/v1/meters/{meter_id}/consumption` | Consumption history only. |
| GET | `/health` | Liveness check. |

## Sample request / response

```bash
curl http://127.0.0.1:8000/api/v1/meters/J100005
```

```json
{
  "meter_id": "J100005",
  "serial_no": "HP63682",
  "make": "Allied",
  "phase_type": "three",
  "installation_status": "Faulty",
  "installation_type": "Whole Current",
  "hierarchy": [
    "Jaipur Zone 3 (Z-03)",
    "Circle 6 (C-06)",
    "Division 6 (D-06)",
    "Subdivision 6 (SD-06)",
    "Substation 6 (SS-06)",
    "Feeder 6 (F-006)",
    "Jhotwara DT 6 (DT-006)"
  ],
  "location": {
    "latitude": 26.84670538836401,
    "longitude": 75.86828425070057
  },
  "consumption": [
    {
      "timestamp": "23/06/2026 23:30",
      "kwh": 3662.84,
      "kvah": 3955.87,
      "volt_r": 221
    }
  ]
}
```
(`consumption` is truncated above — the real response contains ~336
half-hourly readings; see PROTOCOL.md for why that number specifically.)

## Assumptions

- The portal's `POST /login` JSON response
  (`{"type":"redirect","status":303,"location":"/meters"}`) is a
  SvelteKit form-action artifact, not a real HTTP redirect — the actual
  HTTP status is 200. The client treats a 200 response as a successful
  login and relies entirely on the `Set-Cookie` header, ignoring the
  JSON body's own "status" field.
- The energy/consumption endpoint's fixed ~7-day window (336 rows at
  30-minute resolution, no visible `from`/`to` params) is a genuine
  server-side limitation, not something this client is failing to
  unlock. No further pagination was attempted against it.
- `q=""` on the search endpoint returning the full, correctly-paginated
  meter list is assumed to be the intended way to enumerate every meter
  (rather than a special "bulk export" endpoint existing separately,
  which wasn't found).
- Numeric fields in the portal's own JSON (lat/long, kwh/kvah/volt) are
  sent as strings and are cast to floats in this API's response models.

## Design decisions & trade-offs

- **HTML parsing over guessed JSON for the nameplate/hierarchy fields.**
  The meter detail page (`/meters/{id}`) is server-rendered HTML, not a
  JSON endpoint (unlike search, geo, and energy). Rather than guess at
  an undiscovered JSON endpoint for it, the adapter parses the real HTML
  with BeautifulSoup, matching on label text for nameplate fields and on
  `main nav` for the hierarchy breadcrumb (see PROTOCOL.md and
  REFLECTION.md for how that selector was arrived at).
- **One composite endpoint (`GET /meters/{id}`) instead of three separate
  ones for nameplate/geo/energy.** The portal itself loads these as three
  separate requests, but callers of this API almost always want the full
  picture at once, so the adapter fetches all three and returns one
  object. `GET /meters/{id}/consumption` is kept as a separate endpoint
  too, for callers who only want the time series (e.g. for charting)
  without the overhead of the HTML parse.
- **Auto re-authentication on 401 / redirect-to-login**, rather than a
  proactive token-refresh timer. Simpler, and correct as long as request
  volume is low enough that a session expiring mid-burst is rare — see
  "what I'd improve" below for where this would need to change.
- **No caching layer.** Every API call hits the real portal live. This
  keeps the implementation simple and the data always fresh, at the cost
  of latency and load on the portal for repeated identical requests.

## What I intentionally left out

- The **network hierarchy explorer** and **local index/query layer**
  extensions (filtering across attributes, "what's near this location")
  — the core 4 required endpoints were the priority within the time box.
- **Caching / freshness** — every call is live; no TTL or invalidation
  logic.
- **The `/transformers` tab** on the portal was not investigated at all
  — out of scope for the meter-focused endpoints required.
- **A bulk/full-dataset endpoint search** beyond confirming that
  `search?q=""` paginates through everything — I didn't look for a
  separate CSV/export-style endpoint.
- **Automated tests.** Given the time budget, verification was done
  manually against the live portal via Swagger UI rather than with a
  test suite (see REFLECTION.md for whether that was the right call).
- **A modern web client** on top of the API (optional extension) — not
  attempted.

## What I'd improve with more time

- Add a small automated test suite (even a handful of `pytest` cases
  hitting a mocked portal) instead of relying on manual Swagger UI
  checks.
- Actually test session-expiry behaviour against a live 1-hour timeout,
  rather than only defensively handling 401/redirect-to-login without
  having observed a real expiry.
- Look into whether the energy endpoint truly has no earlier data
  available (e.g. by trying date-range-shaped query params speculatively)
  before concluding the 7-day window is a hard server-side limit.
- Add basic caching (even an in-memory TTL cache) for the meter list,
  since that data changes far less often than consumption readings.
- Build the network hierarchy explorer as a real extension, using the
  breadcrumb data already being parsed per-meter.
