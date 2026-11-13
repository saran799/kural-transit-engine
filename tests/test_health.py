"""
Tests for Health and Metadata endpoint.
"""

from app.api.routes.health import get_health


def test_health_endpoint():
    data = get_health()
    
    assert data.status == "healthy"
    assert data.agencies_count == 3
    assert data.routes_count == 5402
    assert data.active_routes_count == 4725
    assert data.inactive_routes_count == 677
    assert data.trips_count == 48435
    assert data.stops_count == 6542
    assert data.stop_times_count == 1389081
    
    # Check agency presence
    agency_ids = [a["agency_id"] for a in data.agencies]
    assert "69" in agency_ids
    assert "CMRL" in agency_ids
    assert "SR" in agency_ids
    
    # Check disclaimer
    assert "Real-time" in data.data_source_notice or "live" in data.data_source_notice.lower()
