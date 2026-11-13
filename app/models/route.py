"""
Route models for Kural Transit Engine.
"""

from typing import Optional, List
from pydantic import BaseModel


class RouteResponse(BaseModel):
    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int
    agency_id: str
    agency_name: str
    mode_name: str
    active_trips_count: int


class RouteSearchResponse(BaseModel):
    total: int
    query: Optional[str] = None
    routes: List[RouteResponse]

