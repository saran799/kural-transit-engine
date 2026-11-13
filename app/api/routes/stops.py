"""
Stops API endpoints for Kural Transit Engine.
"""

from typing import Optional
from fastapi import APIRouter, Query
from app.models.stop import StopSearchResponse
from app.services.stop_service import search_stops

router = APIRouter(prefix="/api/stops", tags=["Stops"])


@router.get("/search", response_model=StopSearchResponse)
def get_stops_search(
    query: Optional[str] = Query(default=None, description="Stop name or ID substring (e.g. 'Poonamallee', 'Porur', 'Guindy')"),
    lat: Optional[float] = Query(default=None, description="Latitude for radial search"),
    lon: Optional[float] = Query(default=None, description="Longitude for radial search"),
    radius_m: float = Query(default=1000.0, ge=50.0, le=5000.0, description="Search radius in meters"),
    agency_id: Optional[str] = Query(default=None, description="Filter by agency ('69' for MTC, 'CMRL' for Metro, 'SR' for Suburban Rail)"),
    active_only: bool = Query(default=False, description="Filter only stops with active scheduled trips"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of stops to return"),
):
    """
    Search stops by text query or geographic proximity radius.
    """
    # Normalize if called directly outside FastAPI dependency injection
    lat_val = float(lat) if (lat is not None and not hasattr(lat, "default")) else (lat.default if hasattr(lat, "default") else None)
    lon_val = float(lon) if (lon is not None and not hasattr(lon, "default")) else (lon.default if hasattr(lon, "default") else None)
    query_val = str(query) if (query is not None and not hasattr(query, "default")) else None
    agency_val = str(agency_id) if (agency_id is not None and not hasattr(agency_id, "default")) else None
    active_val = bool(active_only) if not hasattr(active_only, "default") else False
    limit_val = int(limit) if not hasattr(limit, "default") else 20
    radius_val = float(radius_m) if not hasattr(radius_m, "default") else 1000.0

    return search_stops(
        query=query_val,
        lat=lat_val,
        lon=lon_val,
        radius_m=radius_val,
        agency_id=agency_val,
        active_only=active_val,
        limit=limit_val,
    )
