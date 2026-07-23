"""
Adapter layer for the legacy "Urja Meter Ops" portal.

This module is the ONLY place that talks to the real portal. Everything
above it (the FastAPI routes) only ever sees clean Python objects / dicts -
never raw HTML, cookies, or portal-specific quirks.

Findings this client relies on (see PROTOCOL.md for the full write-up):

  * Auth: POST {base}/login as multipart/form-data (fields: email, password).
    On success the portal responds 200 with a JSON body describing a client
    side redirect (`{"type":"redirect","status":303,"location":"/meters"}`)
    rather than a real HTTP redirect, and sets a session cookie
    (`__Secure-better-auth.session_token`, Max-Age=3600s / 1 hour).
    We don't parse that JSON for anything - the cookie is all we need, and
    httpx's cookie jar picks it up automatically.

  * Listing / search: GET {base}/portal/meters/search?q=<query>&page=<n>
    Returns JSON: {"data": [...], "total": N, "page": N, "pageSize": N}.
    Each item: meterId, serialNo, make, phaseType, installStatus, dtCode.
    q="" returns the unfiltered, paginated full list - this is how we
    enumerate all meters (q is required as a param but can be empty).

  * Meter detail: the /meters/{id} page is server-rendered HTML containing
    the nameplate fields and the network hierarchy breadcrumb
    (Zone > Circle > Division > Subdivision > Substation > Feeder > DT).
    We parse that HTML rather than guessing at an undiscovered JSON shape
    for it, since we only ever confirmed HTML for this particular page.

  * Geo: GET {base}/portal/meters/{id}/geo -> {"data": {"latitude": "...",
    "longitude": "..."}}

  * Energy / consumption: GET {base}/portal/meters/{id}/energy -> {"data": [
    {"timestamp": "DD/MM/YYYY HH:MM", "kwh": "...", "kvah": "...",
    "voltR": "..."}, ...]}. Observed response covers exactly a trailing
    7-day window at 30-minute resolution (336 rows) with no visible
    from/to page params - looks like a fixed window rather than something
    we can query further back. TREAT THIS AS UNCONFIRMED until you check
    the Request URL / query string in DevTools; if there IS a date-range
    param, wire it up as `from_`/`to` args below instead of hardcoding.

  !! TODO (verify against your own DevTools Network > Headers tab): !!
  The exact paths for geo/energy below (GEO_PATH / ENERGY_PATH) are a
  reasonable inference from the "geo" / "energy" names Chrome showed in
  the Network panel, but were not double-checked against the actual
  Request URL. Confirm them and update the two constants below if they
  differ (e.g. if the real path is /api/meters/{id}/geo instead of
  /portal/meters/{id}/geo).
"""
from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.config import settings

LOGIN_PATH = "/login"
SEARCH_PATH = "/portal/meters/search"
METER_DETAIL_PATH = "/meters/{meter_id}"

# TODO: confirm these two against DevTools (see docstring above)
GEO_PATH = "/portal/meters/{meter_id}/geo"
ENERGY_PATH = "/portal/meters/{meter_id}/energy"


class PortalAuthError(Exception):
    """Raised when we can't establish or maintain a session with the portal."""


class PortalNotFoundError(Exception):
    """Raised when the portal returns a 404 for a resource (e.g. unknown meter id)."""


class UrjaPortalClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.PORTAL_BASE_URL).rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            # The portal's SvelteKit backend enforces same-origin form
            # submissions (it rejects POST /login with 403 "Cross-site POST
            # form submissions are forbidden" if Origin/Referer don't match
            # its own host - a real browser sends these automatically, a
            # bare HTTP client doesn't). We set them once here so every
            # request looks like it's coming from the portal itself.
            headers={
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/login",
            },
        )
        self._authenticated = False

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #
    def login(self) -> None:
        """Authenticate against the portal and store the session cookie."""
        resp = self._client.post(
            LOGIN_PATH,
            data={
                "email": settings.PORTAL_EMAIL,
                "password": settings.PORTAL_PASSWORD,
            },
        )
        if resp.status_code != 200:
            raise PortalAuthError(
                f"Login failed with status {resp.status_code}: {resp.text[:200]}"
            )
        # Session cookie is picked up automatically into self._client.cookies
        # via Set-Cookie. We don't need to inspect the JSON redirect body.
        self._authenticated = True

    def _ensure_authenticated(self) -> None:
        if not self._authenticated:
            self.login()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """
        Make an authenticated request, auto re-logging-in once if the
        session looks like it has expired (401, or a redirect back to
        /login).
        """
        self._ensure_authenticated()
        resp = self._client.request(method, path, **kwargs)

        session_expired = resp.status_code == 401 or resp.url.path.rstrip("/") == "/login"
        if session_expired:
            self._authenticated = False
            self.login()
            resp = self._client.request(method, path, **kwargs)

        if resp.status_code == 404:
            raise PortalNotFoundError(f"{method} {path} -> 404")

        resp.raise_for_status()
        return resp

    # ------------------------------------------------------------------ #
    # Meters - list / search
    # ------------------------------------------------------------------ #
    def search_meters(self, query: str = "", page: int = 1) -> dict[str, Any]:
        resp = self._request(
            "GET", SEARCH_PATH, params={"q": query, "page": page}
        )
        return resp.json()

    def iter_all_meters(self, page_size: int | None = None):
        """
        Generator that pages through the ENTIRE meter list using q="".
        Useful for a bulk-export / full-dataset extension.
        """
        page = 1
        while True:
            result = self.search_meters(query="", page=page)
            data = result.get("data", [])
            if not data:
                return
            for item in data:
                yield item
            total = result.get("total", 0)
            fetched = page * result.get("pageSize", page_size or settings.DEFAULT_PAGE_SIZE)
            if fetched >= total:
                return
            page += 1

    # ------------------------------------------------------------------ #
    # Meter detail (nameplate + hierarchy) - HTML, parsed
    # ------------------------------------------------------------------ #
    def get_meter_nameplate(self, meter_id: str) -> dict[str, Any]:
        resp = self._request("GET", METER_DETAIL_PATH.format(meter_id=meter_id))
        soup = BeautifulSoup(resp.text, "html.parser")

        def field(label: str) -> str | None:
            """
            Nameplate fields are rendered as label/value pairs. We find the
            element containing the label text and take the text of its
            next sibling element as the value. This is deliberately
            tolerant of exact tag/class names since we didn't capture the
            raw DOM structure - if this breaks, inspect the Elements tab
            for the real tag/class and tighten this selector.
            """
            label_el = soup.find(string=re.compile(rf"^\s*{re.escape(label)}\s*$"))
            if not label_el:
                return None
            container = label_el.find_parent()
            if not container:
                return None
            value_el = container.find_next_sibling()
            return value_el.get_text(strip=True) if value_el else None

        # The breadcrumb is a <nav> element, but it's not the FIRST <nav> in
        # the document - the page header has its own <nav> (Meters |
        # Transformers) that comes earlier and would wrongly match a plain
        # soup.find("nav"). The breadcrumb nav lives inside <main>, right
        # after the <h1>, so scoping the search to `main nav` gets the right
        # one. (Confirmed via DevTools Elements tab against a live page.)
        breadcrumb_el = soup.select_one("main nav")
        hierarchy: list[str] = []
        if breadcrumb_el:
            hierarchy = [
                s.strip()
                for s in breadcrumb_el.get_text(" > ", strip=True).split(">")
                if s.strip()
            ]

        return {
            "meter_id": field("Meter ID") or meter_id,
            "serial_no": field("Serial No"),
            "make": field("Make"),
            "phase_type": field("Phase Type"),
            "installation_status": field("Installation Status"),
            "installation_type": field("Installation Type"),
            "hierarchy": hierarchy,
        }

    # ------------------------------------------------------------------ #
    # Geo
    # ------------------------------------------------------------------ #
    def get_meter_geo(self, meter_id: str) -> dict[str, Any] | None:
        resp = self._request("GET", GEO_PATH.format(meter_id=meter_id))
        body = resp.json()
        data = body.get("data")
        if not data:
            return None
        return {
            "latitude": float(data["latitude"]),
            "longitude": float(data["longitude"]),
        }

    # ------------------------------------------------------------------ #
    # Energy / consumption
    # ------------------------------------------------------------------ #
    def get_meter_energy(self, meter_id: str) -> list[dict[str, Any]]:
        resp = self._request("GET", ENERGY_PATH.format(meter_id=meter_id))
        body = resp.json()
        rows = body.get("data", [])
        cleaned = []
        for row in rows:
            cleaned.append(
                {
                    "timestamp": row["timestamp"],  # kept as-is; see models.py for parsing
                    "kwh": float(row["kwh"]),
                    "kvah": float(row["kvah"]),
                    "volt_r": float(row["voltR"]),
                }
            )
        return cleaned

    # ------------------------------------------------------------------ #
    # Composite: everything about one meter in one call
    # ------------------------------------------------------------------ #
    def get_meter_full(self, meter_id: str) -> dict[str, Any]:
        nameplate = self.get_meter_nameplate(meter_id)
        geo = self.get_meter_geo(meter_id)
        energy = self.get_meter_energy(meter_id)
        return {**nameplate, "location": geo, "consumption": energy}

    def close(self) -> None:
        self._client.close()
