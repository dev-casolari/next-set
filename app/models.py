from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DJSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    youtube_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str = Field(min_length=1)
    genres: list[str] = Field(min_length=1)
    duration_minutes: float = Field(gt=0, allow_inf_nan=False)
    year: int = Field(ge=1000, le=9999)


class CatalogResponse(BaseModel):
    fetched_at: datetime
    items: list[DJSet]
