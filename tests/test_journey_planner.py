"""
Comprehensive journey planning test suite for Kural Transit Engine.
"""

from app.api.routes.journey import post_plan_journey
from app.models.journey import JourneyPlanRequest, Coordinate


def test_direct_journey_general():
    """General journey search from Poonamallee to Porur without route filter."""
    req = JourneyPlanRequest(
        source="Poonamallee",
        destination="Porur",
        departure_time="08:30:00",
        language="en"
    )
    data = post_plan_journey(req)
    assert data.status == "success"
    assert data.direct_journeys_found > 0
    assert len(data.journeys) > 0
    # First journey should be ranked best
    assert data.journeys[0].ranking_score <= data.journeys[-1].ranking_score


def test_journey_with_coordinates():
    """Journey plan using geographic coordinates."""
    # Poonamallee bus stop -> Porur junction
    req = JourneyPlanRequest(
        source=Coordinate(lat=13.05087, lon=80.09372),
        destination=Coordinate(lat=13.03465, lon=80.15653),
        departure_time="10:00:00",
    )
    data = post_plan_journey(req)
    assert data.status == "success"
    assert len(data.journeys) > 0
    j = data.journeys[0]
    assert j.total_duration_minutes > 0


def test_transfer_journey_search():
    """Transfer journey search from Poonamallee to Vadapalani."""
    req = JourneyPlanRequest(
        source="MTC-9440",
        destination="MTC-5750",
        departure_time="10:00:00",
        max_transfers=1,
    )
    data = post_plan_journey(req)
    assert data.status in ("success", "no_route_found")
    if data.status == "success":
        assert len(data.journeys) > 0


def test_tamil_localization():
    """Verify Tamil language responses."""
    req = JourneyPlanRequest(
        source="Poonamallee",
        destination="Porur",
        departure_time="11:00:00",
        route_filter="S23",
        language="ta"
    )
    data = post_plan_journey(req)
    assert data.language == "ta"
    assert data.status == "success"
    j = data.journeys[0]
    # Check Tamil disclaimer and leg instructions
    assert "அட்டவணை" in data.data_notice
    assert any("ஏறவும்" in leg.instruction for leg in j.legs)


def test_honest_error_on_unknown_location():
    """Verify honest error reporting for unresolvable locations."""
    req = JourneyPlanRequest(
        source="NonExistentUnknownPlace123",
        destination="Porur",
        departure_time="10:00:00",
    )
    data = post_plan_journey(req)
    assert data.status == "error"
    assert data.error_details is not None
    assert "Could not locate" in data.error_details
    assert len(data.suggestions) > 0


def test_scheduled_vs_live_distinction():
    """Ensure is_live is always False and data notice explicitly states static timetable."""
    req = JourneyPlanRequest(
        source="Poonamallee",
        destination="Porur",
        departure_time="11:50:00",
    )
    data = post_plan_journey(req)
    assert "Real-time" in data.data_notice or "live" in data.data_notice.lower()
    for j in data.journeys:
        assert j.is_live is False
        for leg in j.legs:
            assert leg.is_live is False
            assert leg.schedule_source == "GTFS_STATIC_SCHEDULE"
