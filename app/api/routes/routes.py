"""
Routes API endpoints for Kural Transit Engine.
"""

from typing import Optional
from fastapi import APIRouter, Query
from app.models.route import RouteSearchResponse
from app.services.route_service import search_routes

router = APIRouter(prefix="/api/routes", tags=["Routes"])


@router.get("/search", response_model=RouteSearchResponse)
def get_routes_search(
    query: Optional[str] = Query(default=None, description="Route short name (e.g. 'S23', '29A', '54') or long name"),
    agency_id: Optional[str] = Query(default=None, description="Filter by agency ('69' for MTC, 'CMRL' for Metro, 'SR' for Suburban Rail)"),
    mode: Optional[str] = Query(default=None, description="Filter by mode ('Bus', 'Metro', 'Suburban Rail')"),
    active_only: bool = Query(default=False, description="Filter only routes with scheduled trips in feed"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of routes to return"),
):
    """
    Search transit routes by short name, long name, agency, or mode.
    """
    query_val = str(query) if (query is not None and not hasattr(query, "default")) else None
    agency_val = str(agency_id) if (agency_id is not None and not hasattr(agency_id, "default")) else None
    mode_val = str(mode) if (mode is not None and not hasattr(mode, "default")) else None
    active_val = bool(active_only) if not hasattr(active_only, "default") else False
    limit_val = int(limit) if not hasattr(limit, "default") else 20

    return search_routes(
        query=query_val,
        agency_id=agency_val,
        mode=mode_val,
        active_only=active_val,
        limit=limit_val,
    )
