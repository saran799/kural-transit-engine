"""
First Validation Test Suite: Poonamallee to Porur on Route S23.
Verifies whether a direct S23 journey actually exists in the GTFS records
and returns exact evidence from matching route, trips, and stop_times records.
"""

from app.services.database import get_db
from app.api.routes.journey import post_plan_journey
from app.models.journey import JourneyPlanRequest


def test_gtfs_s23_route_evidence():
    """Verify route record for S23 in GTFS database."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT route_id, route_short_name, route_long_name, route_type, agency_id, active_trips_count
            FROM routes
            WHERE route_short_name = 'S23' AND route_long_name = 'Poonamallee TO Porur'
        """)
        row = cur.fetchone()
        assert row is not None, "Route S23 (Poonamallee TO Porur) MUST exist in routes table"
        assert row["route_id"] == "MTC-18463"
        assert row["route_short_name"] == "S23"
        assert row["route_long_name"] == "Poonamallee TO Porur"
        assert row["route_type"] == 3  # Bus
        assert row["agency_id"] == "69"  # MTC
        assert row["active_trips_count"] == 10, "Route MTC-18463 should have exactly 10 trips"


def test_gtfs_s23_trips_evidence():
    """Verify scheduled trips for route MTC-18463."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT trip_id, route_id, service_id, direction_id
            FROM trips
            WHERE route_id = 'MTC-18463'
            ORDER BY trip_id
        """)
        trips = cur.fetchall()
        assert len(trips) == 10, f"Expected 10 trips for S23, found {len(trips)}"
        trip_ids = [t["trip_id"] for t in trips]
        assert "MTC-70977" in trip_ids
        assert "MTC-70983" in trip_ids
        for t in trips:
            assert t["service_id"] == "MTC-Regular"


def test_gtfs_s23_stop_times_sequence_evidence():
    """Verify exact stop sequence and times for S23 trip MTC-70977 (11:50 AM departure)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT st.stop_sequence, st.stop_id, s.stop_name, st.arrival_time, st.departure_time
            FROM stop_times st
            JOIN stops s ON st.stop_id = s.stop_id
            WHERE st.trip_id = 'MTC-70977'
            ORDER BY st.stop_sequence ASC
        """)
        stops = cur.fetchall()
        assert len(stops) == 12, f"Expected 12 stops for trip MTC-70977, found {len(stops)}"
        
        # Stop 1 must be Poonamallee
        assert stops[0]["stop_sequence"] == 1
        assert stops[0]["stop_id"] == "MTC-9440"
        assert "Poonamallee" in stops[0]["stop_name"]
        assert stops[0]["departure_time"] == "11:50:00"
        
        # Stop 11 must be Porur
        assert stops[10]["stop_sequence"] == 11
        assert stops[10]["stop_id"] == "MTC-5738"
        assert stops[10]["stop_name"] == "Porur"
        assert stops[10]["arrival_time"] == "12:08:00"
        
        # Stop 12 is terminal Porur
        assert stops[11]["stop_sequence"] == 12
        assert stops[11]["stop_id"] == "MTC-9278"
        assert stops[11]["stop_name"] == "Porur"
        assert stops[11]["arrival_time"] == "12:09:00"


def test_journey_planner_api_s23_validation():
    """Test POST /api/journey/plan specifically for Poonamallee to Porur on S23."""
    payload = JourneyPlanRequest(
        source="Poonamallee",
        destination="Porur",
        departure_time="11:00:00",
        route_filter="S23",
        max_transfers=0,
        language="en"
    )
    data = post_plan_journey(payload)
    
    assert data.status == "success"
    assert data.direct_journeys_found > 0
    assert len(data.journeys) > 0
    
    first_journey = data.journeys[0]
    assert first_journey.transfers_count == 0
    assert "S23" in first_journey.summary
    
    # Locate transit leg
    transit_legs = [l for l in first_journey.legs if l.leg_type == "TRANSIT"]
    assert len(transit_legs) == 1
    t_leg = transit_legs[0]
    
    assert t_leg.route_short_name == "S23"
    assert t_leg.route_id == "MTC-18463"
    assert "Poonamallee" in t_leg.departure_stop_name
    assert "Porur" in t_leg.arrival_stop_name
    assert t_leg.departure_time == "11:50:00"
    assert t_leg.arrival_time == "12:08:00"
    assert t_leg.duration_minutes == 18.0
    assert t_leg.stops_count == 10
    assert len(t_leg.intermediate_stops) == 9
    assert t_leg.is_live is False
    assert t_leg.schedule_source == "GTFS_STATIC_SCHEDULE"
