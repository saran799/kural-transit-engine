"""
Tests for Stops search API.
"""

from app.api.routes.stops import get_stops_search


def test_search_stops_by_name():
    data = get_stops_search(query="Poonamallee")
    assert data.total > 0
    stop_names = [s.stop_name for s in data.stops]
    assert any("Poonamallee" in name for name in stop_names)


def test_search_stops_porur():
    data = get_stops_search(query="Porur")
    assert data.total > 0
    stop_names = [s.stop_name for s in data.stops]
    assert any("Porur" in name for name in stop_names)


def test_search_stops_by_coordinates():
    # Coordinates of Poonamallee bus stop: 13.05087, 80.09372
    data = get_stops_search(lat=13.05087, lon=80.09372, radius_m=1000.0)
    assert data.total > 0
    first_stop = data.stops[0]
    assert first_stop.distance_m is not None
    assert first_stop.distance_m < 1000.0


def test_search_stops_agency_filter():
    data = get_stops_search(query="Central", agency_id="CMRL")
    assert data.total > 0
    for s in data.stops:
        assert s.agency_id == "CMRL"
