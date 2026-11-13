"""
Tests for ElevenLabs voice assistant tool endpoint: POST /api/kural/tools/search_journey.
"""

from app.api.routes.journey import search_journey_tool
from app.models.journey import KuralToolJourneyRequest, Coordinate
import pytest
from fastapi import HTTPException


def test_kural_tool_search_journey_success():
    """Test voice tool endpoint with origin, destination, and call_id."""
    req = KuralToolJourneyRequest(
        origin="Poonamallee",
        destination="Porur",
        departure_time="11:00:00",
        language="en",
        call_id="call_test_12345"
    )
    res = search_journey_tool(req)
    assert res.found is True
    assert res.total_options > 0
    assert len(res.options) > 0
    assert "Poonamallee" in res.spoken_response
    assert "Porur" in res.spoken_response
    assert res.call_id == "call_test_12345"
    assert res.raw_plan is not None
    assert res.raw_plan.status == "success"


def test_kural_tool_search_journey_tamil():
    """Test voice tool endpoint with Tamil language output."""
    req = KuralToolJourneyRequest(
        origin="Poonamallee",
        destination="Porur",
        departure_time="11:00:00",
        language="ta",
        call_id="call_tamil_789"
    )
    res = search_journey_tool(req)
    assert res.found is True
    assert "வழிகள் உள்ளன" in res.spoken_response or "பயண நேரம்" in res.spoken_response
    assert res.call_id == "call_tamil_789"


def test_kural_tool_search_journey_with_source_alias():
    """Test voice tool accepting 'source' instead of 'origin'."""
    req = KuralToolJourneyRequest(
        source="Poonamallee",
        destination="Porur",
        departure_time="08:30:00",
    )
    res = search_journey_tool(req)
    assert res.found is True
    assert res.total_options > 0


def test_kural_tool_search_journey_missing_origin_and_source():
    """Test that omitting both origin and source raises HTTP 422 error."""
    req = KuralToolJourneyRequest(
        destination="Porur",
    )
    with pytest.raises(HTTPException) as exc_info:
        search_journey_tool(req)
    assert exc_info.value.status_code == 422
    assert "origin" in exc_info.value.detail or "source" in exc_info.value.detail


def test_kural_tool_search_journey_unresolvable_location():
    """Test voice tool graceful response when an unknown place is queried."""
    req = KuralToolJourneyRequest(
        origin="FakeNonExistentPlace999",
        destination="Porur",
        language="en",
    )
    res = search_journey_tool(req)
    assert res.found is False
    assert res.total_options == 0
    assert "no transit journeys were found" in res.spoken_response.lower() or "sorry" in res.spoken_response.lower()


def test_kural_tool_morning_departure_10am():
    """Test voice tool with explicit morning departure time at 10:00 (HH:MM format)."""
    req = KuralToolJourneyRequest(
        origin="Poonamallee",
        destination="Porur",
        departure_time="10:00",
        language="en"
    )
    res = search_journey_tool(req)
    assert res.found is True
    assert res.total_options > 0
    assert res.raw_plan is not None
    assert res.raw_plan.departure_time == "10:00"
    # Ensure options depart at or after 10:00:00
    for opt in res.options:
        assert opt.departure_time >= "10:00:00"



