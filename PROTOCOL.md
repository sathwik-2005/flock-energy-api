# PROTOCOL.md — How Urja Meter Ops actually works

Findings from manual reconnaissance via Chrome DevTools (Network tab),
against a real logged-in session on `https://urja-ops.flockenergy.tech`.

## Stack fingerprint

The portal appears to be a **SvelteKit** app (chunk names, `_data.json?x-sveltekit-invalidated=...`
requests, and the JSON-encoded-redirect pattern below are all SvelteKit
form-action conventions, not a hand-rolled backend).

## Authentication

- `POST /login`
- Body: **form-encoded** (not JSON) — fields `email`, `password`
- On success: `200 OK`, JSON body: `{"type":"redirect","status":303,"location":"/meters"}`
  - Quirk: this is SvelteKit's form-action response format. The *actual*
    HTTP status is 200, not 303 — the 303 is just data describing where the
    client-side router should navigate. Don't treat this response's stated
    "status" as the real HTTP status.
- Session is a cookie: `__Secure-better-auth.session_token`
  - `Max-Age=3600` (**1 hour**), `HttpOnly; Secure; SameSite=Lax`
  - Cookie name suggests the portal uses the `better-auth` library.
  - No CSRF token observed in the login request.
- **Quirk found during implementation**: the portal enforces a same-origin
  check on `POST /login` at the framework level (SvelteKit's built-in CSRF
  protection). A plain HTTP client that doesn't send `Origin`/`Referer`
  headers matching the portal's own host gets rejected with `403: Cross-site
  POST form submissions are forbidden` — even with a completely correct
  email/password payload. A real browser sends these headers automatically,
  which is why this only surfaces when scripting the login. Fix: explicitly
  set `Origin: https://urja-ops.flockenergy.tech` (and a matching `Referer`)
  on every request from the adapter client.
- No separate logout/refresh endpoint investigated (out of scope — portal
  is read-only for this exercise).

## Session expiry / re-auth

- Not exhaustively tested against a live 1-hour timeout during recon.
- Client-side handling implemented defensively: if any authenticated
  request comes back `401`, or if `httpx`'s followed redirects land back
  on `/login`, we treat the session as expired, re-login once, and retry
  the original request.

## Meters — list & search

- `GET /portal/meters/search?q=<query>&page=<n>`
- `q` can be empty string to get the **unfiltered, paginated full list**
  (this is how the UI's default `/meters` view is populated, and how we
  enumerate every meter for a bulk export).
- Response (`application/json`):
  ```json
  {
    "data": [
      {
        "meterId": "J100005",
        "serialNo": "HP63682",
        "make": "Allied",
        "phaseType": "three",
        "installStatus": "Faulty",
        "dtCode": "DT-006"
      }
    ],
    "total": 403,
    "page": 1,
    "pageSize": 20
  }
  ```
- Search is server-side (confirmed: searching a nonsense string returns
  `"total": 0`, and pagination resets to "Page 1 of 1" — a purely
  client-side filter would never do this).
- Debounced on the frontend (fires ~shortly after typing stops), but as
  an API consumer you just call it directly — no debounce needed server-side.

## Meter detail

- `GET /meters/{meterId}` — server-rendered HTML page containing:
  - **Nameplate**: Meter ID, Serial No, Make, Phase Type, Installation
    Status, Installation Type
  - **Hierarchy breadcrumb**: `Zone > Circle > Division > Subdivision >
    Substation > Feeder > DT`, e.g.
    `Jaipro Zone 3 (Z-03) > Circle 6 (C-06) > Division 6 (D-06) >
    Subdivision 6 (SD-06) > Substation 6 (SS-06) > Feeder 6 (F-006) >
    Jhotwara DT 6 (DT-006)`
  - This page also triggers two further **client-side fetches** for data
    that loads in below the fold:

### Geo

- `GET /portal/meters/{meterId}/geo` — **confirmed working** against a live
  session
- Response: `{"data": {"latitude": "26.846...", "longitude": "75.868..."}}`
  (both as strings, not numbers)

### Energy / consumption

- `GET /portal/meters/{meterId}/energy` — **confirmed working** against a
  live session
- Response: `{"data": [{"timestamp": "DD/MM/YYYY HH:MM", "kwh": "...",
  "kvah": "...", "voltR": "..."}, ...]}`
- Observed payload for one meter: **exactly 336 rows**, spanning
  `23/06/2026 23:30` → `30/06/2026 23:30` — i.e. **a fixed trailing 7-day
  window at 30-minute resolution** (7 × 48 = 336). No `from`/`to`/`page`
  parameters were observed in the request. This looks like a hardcoded
  server-side window rather than something a client can extend — flagged
  as a real limitation, not an oversight in this client.
- All numeric fields arrive as strings and need casting (`"3662.84"` → `3662.84`).

## Known gaps / things not fully verified

- Long-running session behaviour (what happens exactly at the 1-hour
  mark, whether there's a sliding expiry, etc.) was not tested live.
- The `/transformers` tab (visible in the nav) was not investigated —
  out of scope for the required meter endpoints, but likely relevant to
  the optional "network hierarchy" extension.
- Whether a true bulk/export endpoint exists (as opposed to paging
  through `search` with `q=""`) was not investigated.
- The hierarchy breadcrumb on the meter detail page isn't wrapped in an
  obviously-named `<nav>`/`.breadcrumb` element — the client identifies it
  by matching on the hierarchy code pattern (`(Z-03)`, `(C-06)`, etc.)
  rather than a CSS selector, since the actual markup wasn't captured from
  the Elements tab.
