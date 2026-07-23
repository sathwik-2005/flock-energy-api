from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.client import PortalAuthError, PortalNotFoundError, UrjaPortalClient
from app.models import MeterDetail, MeterListResponse

_client: UrjaPortalClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = UrjaPortalClient()
    yield
    _client.close()


app = FastAPI(
    title="Flock Energy - Urja Meter Ops API",
    version="1.0.0",
    description=(
        "Clean REST API in front of the legacy Urja Meter Ops portal. "
        "See /docs for interactive testing, and this repo's PROTOCOL.md "
        "for how the underlying portal actually works."
    ),
    lifespan=lifespan,
)


def get_client() -> UrjaPortalClient:
    assert _client is not None, "Client not initialised - app lifespan didn't run"
    return _client


@app.get("/api/v1/meters", response_model=MeterListResponse, tags=["meters"])
def list_meters(
    q: str = Query("", description="Search by meter number or serial (empty = all meters)"),
    page: int = Query(1, ge=1),
):
    """List/search smart meters. Mirrors the portal's own search+pagination."""
    try:
        return get_client().search_meters(query=q, page=page)
    except PortalAuthError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/meters/{meter_id}", response_model=MeterDetail, tags=["meters"])
def get_meter(meter_id: str):
    """Full detail for one meter: nameplate, hierarchy, location, and consumption."""
    try:
        data = get_client().get_meter_full(meter_id)
        return data
    except PortalNotFoundError:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found")
    except PortalAuthError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/meters/{meter_id}/consumption", tags=["meters"])
def get_meter_consumption(meter_id: str):
    """Consumption history only (subset of the full meter detail)."""
    try:
        return {"meter_id": meter_id, "consumption": get_client().get_meter_energy(meter_id)}
    except PortalNotFoundError:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found")
    except PortalAuthError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
