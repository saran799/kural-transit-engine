"""
Direct API validation script.
Tests all endpoints and verifies Poonamallee to Porur S23 journey.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.api.routes.health import get_health
from app.api.routes.stops import get_stops_search
from app.api.routes.routes import get_routes_search
from app.api.routes.journey import post_plan_journey
from app.models.journey import JourneyPlanRequest

print("=" * 60)
print("1. HEALTH CHECK ENDPOINT")
print("=" * 60)
h = get_health()
print(f"Status: {h.status}")
print(f"Total Agencies: {h.agencies_count}")
print(f"Total Routes: {h.routes_count} (Active: {h.active_routes_count}, Inactive: {h.inactive_routes_count})")
print(f"Total Trips: {h.trips_count}")
print(f"Total Stops: {h.stops_count} (Active: {h.active_stops_count})")
print(f"Total Stop Times: {h.stop_times_count}")
print(f"Agencies: {[a['agency_name'] for a in h.agencies]}")
print(f"Notice: {h.data_source_notice}")

print("\n" + "=" * 60)
print("2. STOPS SEARCH (Poonamallee and Porur)")
print("=" * 60)
pml_stops = get_stops_search(query="Poonamallee", limit=5)
print(f"Poonamallee stops found: {pml_stops.total}")
for s in pml_stops.stops:
    print(f"  - {s.stop_id}: {s.stop_name} ({s.stop_lat}, {s.stop_lon}) [Active: {s.is_active}]")

porur_stops = get_stops_search(query="Porur", limit=5)
print(f"Porur stops found: {porur_stops.total}")
for s in porur_stops.stops:
    print(f"  - {s.stop_id}: {s.stop_name} ({s.stop_lat}, {s.stop_lon}) [Active: {s.is_active}]")

print("\n" + "=" * 60)
print("3. ROUTES SEARCH (S23)")
print("=" * 60)
s23_routes = get_routes_search(query="S23")
print(f"Routes found for 'S23': {s23_routes.total}")
for r in s23_routes.routes:
    print(f"  - {r.route_id} | Short: {r.route_short_name} | Long: {r.route_long_name} | Trips: {r.active_trips_count} | Mode: {r.mode_name} | Agency: {r.agency_name}")

print("\n" + "=" * 60)
print("4. FIRST VALIDATION: POONAMALLEE TO PORUR S23 DIRECT JOURNEY")
print("=" * 60)
req = JourneyPlanRequest(
    source="Poonamallee",
    destination="Porur",
    departure_time="11:00:00",
    route_filter="S23",
    language="en",
    max_transfers=0
)
res = post_plan_journey(req)
print(f"Journey Status: {res.status}")
print(f"Direct Journeys Found: {res.direct_journeys_found}")
print(f"Source Resolved: {res.source_resolved}")
print(f"Destination Resolved: {res.destination_resolved}")
print(f"Data Notice: {res.data_notice}")

assert res.status == "success", "Expected journey planning success"
assert len(res.journeys) > 0, "Expected at least one S23 journey"

for i, j in enumerate(res.journeys):
    print(f"\n--- Journey Option #{i+1} ({j.journey_id}) ---")
    print(f"Summary: {j.summary}")
    print(f"Departure: {j.departure_time} | Arrival: {j.arrival_time} | Duration: {j.total_duration_minutes} min")
    print(f"Transfers: {j.transfers_count} | Walking Distance: {j.total_walking_distance_m}m | Live: {j.is_live}")
    print("Legs:")
    for leg in j.legs:
        print(f"  [{leg.leg_sequence}] {leg.leg_type} ({leg.mode}): {leg.departure_stop_name} ({leg.departure_time}) -> {leg.arrival_stop_name} ({leg.arrival_time}) | {leg.duration_minutes} min")
        print(f"      Instruction: {leg.instruction}")
        if leg.intermediate_stops:
            print(f"      Intermediate Stops ({len(leg.intermediate_stops)} stops):")
            for istop in leg.intermediate_stops:
                print(f"        * Seq {istop.stop_sequence}: {istop.stop_name} ({istop.arrival_time})")

print("\n" + "=" * 60)
print("5. TAMIL LOCALIZATION TEST")
print("=" * 60)
req_ta = JourneyPlanRequest(
    source="Poonamallee",
    destination="Porur",
    departure_time="11:00:00",
    route_filter="S23",
    language="ta",
)
res_ta = post_plan_journey(req_ta)
print(f"Language: {res_ta.language}")
print(f"Notice: {res_ta.data_notice}")
if res_ta.journeys:
    j_ta = res_ta.journeys[0]
    print(f"Tamil Summary: {j_ta.summary}")
    for leg in j_ta.legs:
        print(f"  [{leg.leg_sequence}] {leg.mode} - {leg.instruction}")

print("\nAll direct verifications passed successfully!")
