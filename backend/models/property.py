from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator


class Property(BaseModel):
    id: str
    title: str
    price: Optional[float] = None
    price_per_m2: Optional[float] = None
    size_m2: Optional[float] = None
    rooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    url: str
    platform: str  # "idealista" | "habitaclia" | "fotocasa" | "pisos"
    images: list[str] = []
    description: Optional[str] = None
    has_elevator: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_terrace: Optional[bool] = None
    is_new_development: Optional[bool] = None
    published_at: Optional[datetime] = None
    scraped_at: datetime = datetime.utcnow()

    @field_validator("price_per_m2", mode="before")
    @classmethod
    def compute_price_per_m2(cls, v, info):
        if v is not None:
            return v
        data = info.data
        price = data.get("price")
        size = data.get("size_m2")
        if price and size and size > 0:
            return round(price / size, 2)
        return None

    model_config = {"populate_by_name": True}


class SearchFilters(BaseModel):
    city: str
    district: Optional[str] = None  # Barrio o zona específica
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    rooms_min: Optional[int] = None
    size_min: Optional[float] = None
    size_max: Optional[float] = None
    platforms: list[str] = ["idealista"]
    page: int = 1


class SearchResponse(BaseModel):
    total: int
    page: int
    results: list[Property]
    platforms_queried: list[str]
