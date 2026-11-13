"""
Stop models for Kural Transit Engine.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class StopResponse(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    location_type: int = 0
    parent_station: Optional[str] = None
    agency_id: str
    is_active: int = 1
    distance_m: Optional[float] = None
    walk_duration_min: Optional[float] = None


class StopSearchResponse(BaseModel):
    total: int
    query: Optional[str] = None
    stops: List[StopResponse]

