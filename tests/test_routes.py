"""
Tests for Routes search API.
"""

from app.api.routes.routes import get_routes_search


def test_search_route_s23():
    data = get_routes_search(query="S23")
    assert data.total > 0
    
    # Check that S23 Poonamallee to Porur is present
    long_names = [r.route_long_name for r in data.routes]
    assert any("Poonamallee TO Porur" in ln for ln in long_names)
    assert any("Porur TO Poonamallee" in ln for ln in long_names)


def test_search_metro_routes():
    data = get_routes_search(agency_id="CMRL", limit=50)
    assert data.total == 28
    for r in data.routes:
        assert r.agency_id == "CMRL"
        assert r.mode_name == "Metro"


def test_search_suburban_routes():
    data = get_routes_search(agency_id="SR")
    assert data.total > 0
    for r in data.routes:
        assert r.agency_id == "SR"
        assert r.mode_name == "Suburban Rail"


def test_search_active_only():
    data = get_routes_search(active_only=True, limit=50)
    for r in data.routes:
        assert r.active_trips_count > 0
