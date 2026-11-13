"""
Health check models for Kural Transit Engine.
"""

from typing import List, Dict, Any
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    description: str
    agencies_count: int
    routes_count: int
    active_routes_count: int
    inactive_routes_count: int
    trips_count: int
    stops_count: int
    active_stops_count: int
    stop_times_count: int
    agencies: List[Dict[str, Any]]
    routes_by_agency: List[Dict[str, Any]]
    coverage_dates: Dict[str, Any]
    data_source_notice: str

