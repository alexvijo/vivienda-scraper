from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.property import SearchFilters, SearchResponse
from services.search_service import SearchService

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
_search_service = SearchService()


@router.get("/search", response_model=SearchResponse)
def search_properties(
    city: str = Query(..., description="City name (e.g. madrid, barcelona)"),
    price_min: Optional[float] = Query(None, ge=0),
    price_max: Optional[float] = Query(None, ge=0),
    rooms_min: Optional[int] = Query(None, ge=1),
    size_min: Optional[float] = Query(None, ge=0),
    size_max: Optional[float] = Query(None, ge=0),
    platforms: list[str] = Query(default=["idealista"]),
    page: int = Query(1, ge=1),
) -> SearchResponse:
    if not city.strip():
        raise HTTPException(status_code=400, detail="city parameter is required")

    filters = SearchFilters(
        city=city.strip().lower(),
        price_min=price_min,
        price_max=price_max,
        rooms_min=rooms_min,
        size_min=size_min,
        size_max=size_max,
        platforms=platforms,
        page=page,
    )

    properties, queried = _search_service.search(filters)

    return SearchResponse(
        total=len(properties),
        page=page,
        results=properties,
        platforms_queried=queried,
    )


@router.get("/platforms")
def get_platforms() -> list[dict]:
    """Returns the list of supported platforms and their availability."""
    return _search_service.available_platforms()
