"""
Health and status endpoint for Kural Transit Engine.
"""

from fastapi import APIRouter
from app.config import settings
from app.models.health import HealthResponse
from app.services.database import get_database_stats

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health():
    """
    System health check and GTFS dataset statistics.
    Returns counts of agencies, routes, active trips, stops, and service calendars.
    """
    stats = get_database_stats()
    
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        agencies_count=stats["agencies_count"],
        routes_count=stats["routes_count"],
        active_routes_count=stats["active_routes_count"],
        inactive_routes_count=stats["inactive_routes_count"],
        trips_count=stats["trips_count"],
        stops_count=stats["stops_count"],
        active_stops_count=stats["active_stops_count"],
        stop_times_count=stats["stop_times_count"],
        agencies=stats["agencies"],
        routes_by_agency=stats["routes_by_agency"],
        coverage_dates={
            "calendars": stats["service_calendars"],
            "dataset_publisher": "Ithu Ungal Soththu (ChennaiGTFS)",
            "dataset_version": "0.2.0",
        },
        data_source_notice="Scheduled timetable static feed. Real-time live vehicle tracking is not available.",
    )

