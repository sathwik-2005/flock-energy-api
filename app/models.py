from typing import Optional

from pydantic import BaseModel, Field


class MeterSummary(BaseModel):
    """One row from the meters list/search endpoint."""
    meter_id: str = Field(alias="meterId")
    serial_no: str = Field(alias="serialNo")
    make: str
    phase_type: str = Field(alias="phaseType")
    installation_status: str = Field(alias="installStatus")
    dt_code: str = Field(alias="dtCode")

    class Config:
        populate_by_name = True


class MeterListResponse(BaseModel):
    data: list[MeterSummary]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    class Config:
        populate_by_name = True


class GeoLocation(BaseModel):
    latitude: float
    longitude: float


class ConsumptionReading(BaseModel):
    timestamp: str  # kept as portal's own "DD/MM/YYYY HH:MM" string, see README notes
    kwh: float
    kvah: float
    volt_r: float


class MeterDetail(BaseModel):
    meter_id: str
    serial_no: Optional[str] = None
    make: Optional[str] = None
    phase_type: Optional[str] = None
    installation_status: Optional[str] = None
    installation_type: Optional[str] = None
    hierarchy: list[str] = []
    location: Optional[GeoLocation] = None
    consumption: list[ConsumptionReading] = []
