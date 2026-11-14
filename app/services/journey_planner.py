"""
Multimodal Journey Planner for Kural Transit Engine.
Computes direct journeys and transfer journeys across MTC Bus, CMRL Metro, and Southern Railway.
Respects stop sequences, timetable schedules, service calendars, and walking interchanges.
"""

import re
import datetime
from typing import List, Dict, Any, Optional, Tuple, Set, Union
import sqlite3
from app.config import settings
from app.models.journey import (
    JourneyPlanRequest,
    JourneyPlanResponse,
    JourneyOption,
    JourneyLeg,
    IntermediateStop,
    Coordinate,
)
from app.services.database import get_db
from app.services.geocoding import (
    resolve_location,
    haversine_distance,
    get_stop_by_id,
)
from app.services.localization import (
    get_text,
    get_mode_name,
    get_agency_name,
    get_disclaimer,
)

IST_TIMEZONE = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

MODE_NORMALIZATION: Dict[str, str] = {
    "bus": "Bus",
    "buses": "Bus",
    "metro": "Metro",
    "train": "Suburban Rail",
    "trains": "Suburban Rail",
    "suburban": "Suburban Rail",
    "suburban rail": "Suburban Rail",
    "rail": "Suburban Rail",
    "railway": "Suburban Rail",
}


def normalize_modes_filter(modes: Optional[Union[List[str], str]]) -> Optional[List[str]]:
    """Normalize user mode input to canonical database values: ['Bus', 'Metro', 'Suburban Rail']."""
    if not modes:
        return None
    if isinstance(modes, str):
        mode_list = [modes]
    else:
        mode_list = list(modes)

    normalized: Set[str] = set()
    for m in mode_list:
        if not m:
            continue
        cleaned = str(m).strip().lower()
        if cleaned in ("all", "any", "transit", "public transport", "everything"):
            return None
        canon = MODE_NORMALIZATION.get(cleaned, cleaned.title())
        normalized.add(canon)

    return list(normalized) if normalized else None


def parse_departure_time(t_str: Optional[str]) -> Tuple[int, str]:
    """
    Parse a flexible departure time string into (seconds_from_midnight, 'HH:MM:SS').
    Supports:
      - None / empty: current Indian Standard Time (Asia/Kolkata, UTC+5:30)
      - HH:MM:SS / HH:MM
      - 12-hour AM/PM e.g. '10:00 AM', '10:00am', '10 AM', '2:30 PM'
    """
    if not t_str or not str(t_str).strip():
        now_ist = datetime.datetime.now(IST_TIMEZONE)
        sec = now_ist.hour * 3600 + now_ist.minute * 60 + now_ist.second
        return sec, now_ist.strftime("%H:%M:%S")

    raw = str(t_str).strip()

    # 1. Check for 12-hour AM/PM format (e.g. '10:00 AM', '10 AM', '2:30 PM')
    match_12h = re.match(r"^(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(AM|PM|am|pm)$", raw, re.IGNORECASE)
    if match_12h:
        h = int(match_12h.group(1))
        m = int(match_12h.group(2) or 0)
        s = int(match_12h.group(3) or 0)
        period = match_12h.group(4).upper()
        if period == "PM" and h < 12:
            h += 12
        elif period == "AM" and h == 12:
            h = 0
        sec = h * 3600 + m * 60 + s
        return sec, f"{h:02d}:{m:02d}:{s:02d}"

    # 2. Check for HH:MM:SS or HH:MM
    parts = raw.split(":")
    if len(parts) >= 2:
        try:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            sec = h * 3600 + m * 60 + s
            return sec, f"{h:02d}:{m:02d}:{s:02d}"
        except ValueError:
            pass

    # 3. Check for single integer hour e.g. "10"
    if raw.isdigit():
        h = int(raw)
        if 0 <= h <= 24:
            return h * 3600, f"{h:02d}:00:00"

    # Fallback to current IST
    now_ist = datetime.datetime.now(IST_TIMEZONE)
    sec = now_ist.hour * 3600 + now_ist.minute * 60 + now_ist.second
    return sec, now_ist.strftime("%H:%M:%S")


def time_to_sec(t_str: str) -> int:
    """Safe backward-compatible wrapper returning integer seconds from midnight."""
    sec, _ = parse_departure_time(t_str)
    return sec


def sec_to_time(sec: int) -> str:
    """Convert integer seconds to HH:MM:SS string."""
    h = (sec // 3600) % 24
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"



def get_active_service_ids(
    conn: sqlite3.Connection,
    date_str: Optional[str] = None,
    strict_calendar: bool = False
) -> Tuple[List[str], str, int]:
    """
    Get active service_ids for a given date.
    Returns: (list_of_active_service_ids, formatted_date_str, day_of_week_int)
    """
    if date_str:
        try:
            # Handle YYYY-MM-DD or YYYYMMDD
            clean_date = date_str.replace("-", "").strip()
            dt = datetime.datetime.strptime(clean_date, "%Y%m%d")
        except Exception:
            dt = datetime.datetime.now(IST_TIMEZONE)
    else:
        dt = datetime.datetime.now(IST_TIMEZONE)

    date_int = int(dt.strftime("%Y%m%d"))
    date_formatted = dt.strftime("%Y-%m-%d")
    weekday_idx = dt.weekday()  # 0=Monday, 6=Sunday
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_col = days[weekday_idx]

    cur = conn.cursor()
    if strict_calendar:
        cur.execute(f"""
            SELECT service_id 
            FROM calendar 
            WHERE {day_col} = 1 AND start_date <= ? AND end_date >= ?
        """, (date_int, date_int))
    else:
        # Default flexible calendar: verify day of week operation
        cur.execute(f"""
            SELECT service_id 
            FROM calendar 
            WHERE {day_col} = 1
        """)

    active_ids = set(r[0] for r in cur.fetchall())

    # Apply calendar_dates exceptions
    cur.execute("""
        SELECT service_id, exception_type 
        FROM calendar_dates 
        WHERE date = ?
    """, (date_int,))
    for row in cur.fetchall():
        s_id, ex_type = row[0], row[1]
        if ex_type == 1:
            active_ids.add(s_id)
        elif ex_type == 2:
            active_ids.discard(s_id)

    return list(active_ids), date_formatted, weekday_idx


def get_intermediate_stops(
    conn: sqlite3.Connection,
    trip_id: str,
    from_seq: int,
    to_seq: int
) -> List[IntermediateStop]:
    """Retrieve ordered intermediate stops visited between from_seq and to_seq."""
    cur = conn.cursor()
    cur.execute("""
        SELECT st.stop_sequence, st.stop_id, s.stop_name, st.arrival_time, 
               s.stop_lat, s.stop_lon
        FROM stop_times st
        JOIN stops s ON st.stop_id = s.stop_id
        WHERE st.trip_id = ? AND st.stop_sequence > ? AND st.stop_sequence < ?
        ORDER BY st.stop_sequence ASC
    """, (trip_id, from_seq, to_seq))

    results = []
    for r in cur.fetchall():
        results.append(IntermediateStop(
            stop_sequence=r["stop_sequence"],
            stop_id=r["stop_id"],
            stop_name=r["stop_name"],
            arrival_time=r["arrival_time"],
            stop_lat=r["stop_lat"],
            stop_lon=r["stop_lon"],
        ))
    return results


def find_direct_journeys(
    conn: sqlite3.Connection,
    origin_stops: List[Dict[str, Any]],
    dest_stops: List[Dict[str, Any]],
    dep_sec: int,
    active_services: List[str],
    route_filter: Optional[str] = None,
    modes_filter: Optional[List[str]] = None,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Search direct transit connections between candidate origin and destination stops."""
    if not origin_stops or not dest_stops or not active_services:
        return []

    orig_ids = [s["stop_id"] for s in origin_stops]
    dest_ids = [s["stop_id"] for s in dest_stops]

    orig_map = {s["stop_id"]: s for s in origin_stops}
    dest_map = {s["stop_id"]: s for s in dest_stops}

    orig_placeholders = ",".join(["?"] * len(orig_ids))
    dest_placeholders = ",".join(["?"] * len(dest_ids))
    svc_placeholders = ",".join(["?"] * len(active_services))

    query = f"""
    SELECT 
        st1.trip_id,
        t.route_id,
        t.service_id,
        r.route_short_name,
        r.route_long_name,
        r.route_type,
        r.agency_id,
        r.agency_name,
        r.mode_name,
        st1.stop_id as orig_stop_id,
        s1.stop_name as orig_stop_name,
        s1.stop_lat as orig_stop_lat,
        s1.stop_lon as orig_stop_lon,
        st1.departure_sec,
        st1.departure_time,
        st1.stop_sequence as orig_seq,
        st2.stop_id as dest_stop_id,
        s2.stop_name as dest_stop_name,
        s2.stop_lat as dest_stop_lat,
        s2.stop_lon as dest_stop_lon,
        st2.arrival_sec,
        st2.arrival_time,
        st2.stop_sequence as dest_seq,
        (st2.arrival_sec - st1.departure_sec) as transit_duration_sec,
        (st2.stop_sequence - st1.stop_sequence) as stops_traversed
    FROM stop_times st1
    JOIN stop_times st2 ON st1.trip_id = st2.trip_id AND st2.stop_sequence > st1.stop_sequence
    JOIN trips t ON st1.trip_id = t.trip_id
    JOIN routes r ON t.route_id = r.route_id
    JOIN stops s1 ON st1.stop_id = s1.stop_id
    JOIN stops s2 ON st2.stop_id = s2.stop_id
    WHERE st1.stop_id IN ({orig_placeholders})
      AND st2.stop_id IN ({dest_placeholders})
      AND st1.departure_sec >= ?
      AND t.service_id IN ({svc_placeholders})
    """
    params: List[Any] = list(orig_ids) + list(dest_ids) + [dep_sec] + list(active_services)

    if route_filter:
        query += " AND (r.route_short_name = ? COLLATE NOCASE OR r.route_id = ?)"
        params.extend([route_filter.strip(), route_filter.strip()])

    norm_modes = normalize_modes_filter(modes_filter)
    if norm_modes:
        m_placeholders = ",".join(["?"] * len(norm_modes))
        query += f" AND r.mode_name IN ({m_placeholders})"
        params.extend(norm_modes)

    query += " ORDER BY st1.departure_sec ASC LIMIT ?"
    params.append(limit * 2)

    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()

    # Group rows by (trip_id, orig_stop_id) and select the destination stop
    # that minimizes total effective time (transit duration + walk to destination)
    trip_best_candidates: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for r in rows:
        trip_id = r["trip_id"]
        orig_id = r["orig_stop_id"]
        dest_id = r["dest_stop_id"]
        
        o_meta = orig_map[orig_id]
        d_meta = dest_map[dest_id]
        
        orig_walk_s = o_meta.get("walk_duration_sec", 0)
        dest_walk_s = d_meta.get("walk_duration_sec", 0)
        
        total_time_s = r["transit_duration_sec"] + orig_walk_s + dest_walk_s
        
        pair_key = (trip_id, orig_id)
        if pair_key not in trip_best_candidates or total_time_s < trip_best_candidates[pair_key]["total_time_s"]:
            trip_best_candidates[pair_key] = {
                "total_time_s": total_time_s,
                "record": dict(r),
                "orig_walk_dist_m": o_meta.get("distance_m", 0.0),
                "orig_walk_dur_sec": orig_walk_s,
                "dest_walk_dist_m": d_meta.get("distance_m", 0.0),
                "dest_walk_dur_sec": dest_walk_s,
            }

    # Sort selected options by departure time, then total time
    sorted_candidates = sorted(
        trip_best_candidates.values(),
        key=lambda x: (x["record"]["departure_sec"], x["total_time_s"])
    )

    results = []
    seen_route_times: Set[Tuple[str, int]] = set()

    for item in sorted_candidates:
        r_rec = item["record"]
        rt_key = (r_rec["route_id"], r_rec["departure_sec"])
        if rt_key in seen_route_times:
            continue
        seen_route_times.add(rt_key)
        results.append(item)
        if len(results) >= limit:
            break

    return results


def find_transfer_journeys(
    conn: sqlite3.Connection,
    origin_stops: List[Dict[str, Any]],
    dest_stops: List[Dict[str, Any]],
    dep_sec: int,
    active_services: List[str],
    modes_filter: Optional[List[str]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Search 1-transfer transit connections using indexed two-ended window query."""
    if not origin_stops or not dest_stops or not active_services:
        return []

    # Normalize modes filter
    modes_filter = normalize_modes_filter(modes_filter)

    # Pick top candidate origin and destination stops (closest up to 4)
    top_orig = [s["stop_id"] for s in origin_stops[:4]]
    top_dest = [s["stop_id"] for s in dest_stops[:4]]

    orig_map = {s["stop_id"]: s for s in origin_stops}
    dest_map = {s["stop_id"]: s for s in dest_stops}

    orig_placeholders = ",".join(["?"] * len(top_orig))
    dest_placeholders = ",".join(["?"] * len(top_dest))
    svc_placeholders = ",".join(["?"] * len(active_services))

    # Fast 2-ended CTE
    query = f"""
    WITH leg1_trips AS (
        SELECT DISTINCT st1.trip_id, st1.stop_id as orig_stop_id, 
                        st1.departure_sec as dep1_sec, st1.stop_sequence as seq1
        FROM stop_times st1
        JOIN trips t1 ON st1.trip_id = t1.trip_id
        WHERE st1.stop_id IN ({orig_placeholders}) 
          AND st1.departure_sec >= ?
          AND t1.service_id IN ({svc_placeholders})
        ORDER BY st1.departure_sec ASC
        LIMIT 15
    ),
    leg1_reachable AS (
        SELECT l1.trip_id as trip1_id, l1.orig_stop_id, l1.dep1_sec, l1.seq1,
               st2.stop_id as xfer1_stop_id, st2.arrival_sec as arr1_sec, st2.stop_sequence as seq2
        FROM leg1_trips l1
        JOIN stop_times st2 ON l1.trip_id = st2.trip_id AND st2.stop_sequence > l1.seq1
    ),
    leg2_dest AS (
        SELECT st4.trip_id as trip2_id, st4.stop_id as dest_stop_id, 
               st4.arrival_sec as arr2_sec, st4.stop_sequence as seq4
        FROM stop_times st4
        JOIN trips t2 ON st4.trip_id = t2.trip_id
        WHERE st4.stop_id IN ({dest_placeholders})
          AND st4.departure_sec >= ?
          AND st4.departure_sec <= ? + 10800
          AND t2.service_id IN ({svc_placeholders})
        LIMIT 50
    ),
    leg2_reachable AS (
        SELECT d2.trip2_id, d2.dest_stop_id, d2.arr2_sec, d2.seq4,
               st3.stop_id as xfer2_stop_id, st3.departure_sec as dep2_sec, st3.stop_sequence as seq3
        FROM leg2_dest d2
        JOIN stop_times st3 ON d2.trip2_id = st3.trip_id AND st3.stop_sequence < d2.seq4
    )
    SELECT 
        r1.trip1_id, r1.orig_stop_id, r1.dep1_sec, r1.seq1,
        r1.xfer1_stop_id, r1.arr1_sec, r1.seq2,
        r2.trip2_id, r2.xfer2_stop_id, r2.dep2_sec, r2.seq3,
        r2.dest_stop_id, r2.arr2_sec, r2.seq4,
        COALESCE(tr.walk_distance_m, 0.0) as xfer_walk_dist,
        COALESCE(tr.walk_duration_sec, 0) as xfer_walk_sec
    FROM leg1_reachable r1
    JOIN leg2_reachable r2 ON (
        r1.xfer1_stop_id = r2.xfer2_stop_id
        OR EXISTS (SELECT 1 FROM transfers tr_s WHERE tr_s.from_stop_id = r1.xfer1_stop_id AND tr_s.to_stop_id = r2.xfer2_stop_id)
    )
    LEFT JOIN transfers tr ON tr.from_stop_id = r1.xfer1_stop_id AND tr.to_stop_id = r2.xfer2_stop_id
    WHERE r2.dep2_sec >= (r1.arr1_sec + COALESCE(tr.walk_duration_sec, 0) + 180) -- 3 min buffer
      AND (r2.dep2_sec - r1.arr1_sec) <= 3600 -- max 60 min layover
      AND r1.trip1_id != r2.trip2_id
    ORDER BY r2.arr2_sec ASC
    LIMIT ?
    """
    params = (
        list(top_orig) + [dep_sec] + list(active_services) +
        list(top_dest) + [dep_sec, dep_sec] + list(active_services) +
        [limit]
    )

    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()

    results = []
    seen_combos: Set[Tuple[str, str]] = set()

    for r in rows:
        trip1_id = r["trip1_id"]
        trip2_id = r["trip2_id"]
        combo = (trip1_id, trip2_id)
        if combo in seen_combos:
            continue
        seen_combos.add(combo)

        # Retrieve metadata for trip 1 and trip 2
        cur.execute("""
            SELECT r.route_id, r.route_short_name, r.route_long_name, r.route_type,
                   r.agency_id, r.agency_name, r.mode_name,
                   s_orig.stop_name as orig_name, s_orig.stop_lat as orig_lat, s_orig.stop_lon as orig_lon,
                   s_xfer1.stop_name as xfer1_name, s_xfer1.stop_lat as xfer1_lat, s_xfer1.stop_lon as xfer1_lon
            FROM trips t
            JOIN routes r ON t.route_id = r.route_id
            JOIN stops s_orig ON s_orig.stop_id = ?
            JOIN stops s_xfer1 ON s_xfer1.stop_id = ?
            WHERE t.trip_id = ?
        """, (r["orig_stop_id"], r["xfer1_stop_id"], trip1_id))
        meta1 = cur.fetchone()

        cur.execute("""
            SELECT r.route_id, r.route_short_name, r.route_long_name, r.route_type,
                   r.agency_id, r.agency_name, r.mode_name,
                   s_xfer2.stop_name as xfer2_name, s_xfer2.stop_lat as xfer2_lat, s_xfer2.stop_lon as xfer2_lon,
                   s_dest.stop_name as dest_name, s_dest.stop_lat as dest_lat, s_dest.stop_lon as dest_lon
            FROM trips t
            JOIN routes r ON t.route_id = r.route_id
            JOIN stops s_xfer2 ON s_xfer2.stop_id = ?
            JOIN stops s_dest ON s_dest.stop_id = ?
            WHERE t.trip_id = ?
        """, (r["xfer2_stop_id"], r["dest_stop_id"], trip2_id))
        meta2 = cur.fetchone()

        if not meta1 or not meta2:
            continue

        # Check mode filter
        if modes_filter:
            if meta1["mode_name"] not in modes_filter or meta2["mode_name"] not in modes_filter:
                continue

        o_meta = orig_map.get(r["orig_stop_id"], {})
        d_meta = dest_map.get(r["dest_stop_id"], {})

        results.append({
            "raw": dict(r),
            "meta1": dict(meta1),
            "meta2": dict(meta2),
            "orig_walk_dist_m": o_meta.get("distance_m", 0.0),
            "orig_walk_dur_sec": o_meta.get("walk_duration_sec", 0),
            "dest_walk_dist_m": d_meta.get("distance_m", 0.0),
            "dest_walk_dur_sec": d_meta.get("walk_duration_sec", 0),
        })
        if len(results) >= limit:
            break

    return results


def plan_journey(request: JourneyPlanRequest) -> JourneyPlanResponse:
    """Main journey planning function."""
    lang = request.language.lower() if request.language else "en"
    dep_sec, dep_time_str = parse_departure_time(request.departure_time)
    normalized_modes = normalize_modes_filter(request.modes)

    # 1. Resolve source and destination
    orig_candidates, orig_pt, orig_resolved_name = resolve_location(
        request.source, radius_m=request.max_walk_distance_m
    )
    dest_candidates, dest_pt, dest_resolved_name = resolve_location(
        request.destination, radius_m=request.max_walk_distance_m
    )

    now_ist = datetime.datetime.now(IST_TIMEZONE)
    default_date = now_ist.strftime("%Y-%m-%d")

    if not orig_candidates:
        err_msg = get_text(lang, "error_unresolved_stop", query=str(request.source))
        return JourneyPlanResponse(
            status="error",
            language=lang,
            departure_time=dep_time_str,
            service_date=request.date or default_date,
            source_resolved=orig_resolved_name,
            destination_resolved=dest_resolved_name,
            direct_journeys_found=0,
            transfer_journeys_found=0,
            data_notice=get_disclaimer(lang),
            error_details=err_msg,
            suggestions=[
                "Check the stop spelling (e.g. 'Poonamallee', 'Porur', 'Guindy').",
                "Try passing coordinates {lat, lon} directly.",
                "Increase max_walk_distance_m if you are far from a transit stop.",
            ]
        )

    if not dest_candidates:
        err_msg = get_text(lang, "error_unresolved_stop", query=str(request.destination))
        return JourneyPlanResponse(
            status="error",
            language=lang,
            departure_time=dep_time_str,
            service_date=request.date or default_date,
            source_resolved=orig_resolved_name,
            destination_resolved=dest_resolved_name,
            direct_journeys_found=0,
            transfer_journeys_found=0,
            data_notice=get_disclaimer(lang),
            error_details=err_msg,
            suggestions=[
                "Check the stop spelling (e.g. 'Porur', 'Tambaram', 'Central').",
                "Try passing coordinates {lat, lon} directly.",
            ]
        )

    with get_db() as conn:
        # 2. Get active service IDs for calendar
        active_services, date_formatted, _ = get_active_service_ids(
            conn, date_str=request.date, strict_calendar=request.strict_calendar
        )

        journey_options: List[JourneyOption] = []

        # 3. Search Direct Journeys
        direct_results = find_direct_journeys(
            conn,
            origin_stops=orig_candidates,
            dest_stops=dest_candidates,
            dep_sec=dep_sec,
            active_services=active_services,
            route_filter=request.route_filter,
            modes_filter=normalized_modes,
            limit=settings.MAX_JOURNEY_RESULTS,
        )

        journey_idx = 1
        for res in direct_results:
            rec = res["record"]
            legs: List[JourneyLeg] = []
            leg_seq = 1

            # Walk leg 1: Source -> Boarding stop (if > 15m)
            walk1_m = res["orig_walk_dist_m"]
            walk1_s = res["orig_walk_dur_sec"]
            if walk1_m > 15.0 and orig_pt:
                legs.append(JourneyLeg(
                    leg_sequence=leg_seq,
                    leg_type="WALK",
                    mode="Walk",
                    departure_stop_id="ORIGIN",
                    departure_stop_name=orig_resolved_name,
                    departure_time=sec_to_time(dep_sec),
                    departure_coords=Coordinate(lat=orig_pt["lat"], lon=orig_pt["lon"]),
                    arrival_stop_id=rec["orig_stop_id"],
                    arrival_stop_name=rec["orig_stop_name"],
                    arrival_time=sec_to_time(dep_sec + walk1_s),
                    arrival_coords=Coordinate(lat=rec["orig_stop_lat"], lon=rec["orig_stop_lon"]),
                    duration_minutes=round(walk1_s / 60.0, 1),
                    distance_meters=walk1_m,
                    instruction=get_text(
                        lang, "walk_origin",
                        distance=int(walk1_m),
                        stop_name=rec["orig_stop_name"],
                        minutes=max(1, int(walk1_s / 60.0))
                    ),
                    is_live=False,
                    schedule_source="GTFS_STATIC_SCHEDULE",
                ))
                leg_seq += 1

            # Transit leg
            intermediate = get_intermediate_stops(
                conn, rec["trip_id"], rec["orig_seq"], rec["dest_seq"]
            )
            mode_disp = get_mode_name(rec["mode_name"], lang)
            agency_disp = get_agency_name(rec["agency_id"], lang)

            legs.append(JourneyLeg(
                leg_sequence=leg_seq,
                leg_type="TRANSIT",
                mode=rec["mode_name"],
                agency_id=rec["agency_id"],
                agency_name=agency_disp,
                route_id=rec["route_id"],
                route_short_name=rec["route_short_name"],
                route_long_name=rec["route_long_name"],
                trip_id=rec["trip_id"],
                departure_stop_id=rec["orig_stop_id"],
                departure_stop_name=rec["orig_stop_name"],
                departure_time=rec["departure_time"],
                departure_coords=Coordinate(lat=rec["orig_stop_lat"], lon=rec["orig_stop_lon"]),
                arrival_stop_id=rec["dest_stop_id"],
                arrival_stop_name=rec["dest_stop_name"],
                arrival_time=rec["arrival_time"],
                arrival_coords=Coordinate(lat=rec["dest_stop_lat"], lon=rec["dest_stop_lon"]),
                duration_minutes=round(rec["transit_duration_sec"] / 60.0, 1),
                stops_count=rec["stops_traversed"],
                intermediate_stops=intermediate,
                instruction=get_text(
                    lang, "board",
                    mode=mode_disp,
                    route=rec["route_short_name"],
                    route_long=rec["route_long_name"]
                ),
                is_live=False,
                schedule_source="GTFS_STATIC_SCHEDULE",
            ))
            leg_seq += 1

            # Walk leg 2: Alighting stop -> Final destination (if > 15m)
            walk2_m = res["dest_walk_dist_m"]
            walk2_s = res["dest_walk_dur_sec"]
            if walk2_m > 15.0 and dest_pt:
                legs.append(JourneyLeg(
                    leg_sequence=leg_seq,
                    leg_type="WALK",
                    mode="Walk",
                    departure_stop_id=rec["dest_stop_id"],
                    departure_stop_name=rec["dest_stop_name"],
                    departure_time=rec["arrival_time"],
                    departure_coords=Coordinate(lat=rec["dest_stop_lat"], lon=rec["dest_stop_lon"]),
                    arrival_stop_id="DESTINATION",
                    arrival_stop_name=dest_resolved_name,
                    arrival_time=sec_to_time(rec["arrival_sec"] + walk2_s),
                    arrival_coords=Coordinate(lat=dest_pt["lat"], lon=dest_pt["lon"]),
                    duration_minutes=round(walk2_s / 60.0, 1),
                    distance_meters=walk2_m,
                    instruction=get_text(
                        lang, "walk_destination",
                        distance=int(walk2_m),
                        minutes=max(1, int(walk2_s / 60.0))
                    ),
                    is_live=False,
                    schedule_source="GTFS_STATIC_SCHEDULE",
                ))

            # Duration and ranking
            first_dep_sec = dep_sec if (walk1_m > 15.0 and orig_pt) else rec["departure_sec"]
            last_arr_sec = (rec["arrival_sec"] + walk2_s) if (walk2_m > 15.0 and dest_pt) else rec["arrival_sec"]
            total_dur_min = round((last_arr_sec - first_dep_sec) / 60.0, 1)
            tot_walk_m = walk1_m + walk2_m

            # Ranking: Total duration + 1.2 * walking time
            rank_score = total_dur_min + (tot_walk_m / 60.0) * 1.2

            summary = get_text(
                lang, "journey_summary_direct",
                mode=mode_disp,
                route=rec["route_short_name"],
                origin=rec["orig_stop_name"],
                destination=rec["dest_stop_name"]
            )

            journey_options.append(JourneyOption(
                journey_id=f"direct-{journey_idx}",
                summary=summary,
                departure_time=sec_to_time(first_dep_sec),
                arrival_time=sec_to_time(last_arr_sec),
                total_duration_minutes=total_dur_min,
                total_walking_distance_m=round(tot_walk_m, 1),
                transfers_count=0,
                ranking_score=round(rank_score, 2),
                legs=legs,
                is_live=False,
                primary_mode=rec["mode_name"],
                primary_route=rec["route_short_name"],
                boarding_stop=rec["orig_stop_name"],
                destination_stop=rec["dest_stop_name"],
                fare=None,
                data_notice="Scheduled timetable data (GTFS static). Real-time GPS unavailable.",
            ))
            journey_idx += 1

        # 4. Search 1-Transfer Journeys (if max_transfers >= 1 and fewer than 3 direct options found)
        transfer_results_count = 0
        if request.max_transfers >= 1 and not request.route_filter and len(direct_results) < 3:
            transfer_results = find_transfer_journeys(
                conn,
                origin_stops=orig_candidates,
                dest_stops=dest_candidates,
                dep_sec=dep_sec,
                active_services=active_services,
                modes_filter=normalized_modes,
                limit=settings.MAX_JOURNEY_RESULTS,
            )
            transfer_results_count = len(transfer_results)

            t_idx = 1
            for tres in transfer_results:
                raw = tres["raw"]
                m1 = tres["meta1"]
                m2 = tres["meta2"]

                legs: List[JourneyLeg] = []
                leg_seq = 1

                # Walk 1
                w1_m = tres["orig_walk_dist_m"]
                w1_s = tres["orig_walk_dur_sec"]
                if w1_m > 15.0 and orig_pt:
                    legs.append(JourneyLeg(
                        leg_sequence=leg_seq,
                        leg_type="WALK",
                        mode="Walk",
                        departure_stop_id="ORIGIN",
                        departure_stop_name=orig_resolved_name,
                        departure_time=sec_to_time(dep_sec),
                        departure_coords=Coordinate(lat=orig_pt["lat"], lon=orig_pt["lon"]),
                        arrival_stop_id=raw["orig_stop_id"],
                        arrival_stop_name=m1["orig_name"],
                        arrival_time=sec_to_time(dep_sec + w1_s),
                        arrival_coords=Coordinate(lat=m1["orig_lat"], lon=m1["orig_lon"]),
                        duration_minutes=round(w1_s / 60.0, 1),
                        distance_meters=w1_m,
                        instruction=get_text(
                            lang, "walk_origin",
                            distance=int(w1_m),
                            stop_name=m1["orig_name"],
                            minutes=max(1, int(w1_s / 60.0))
                        ),
                        is_live=False,
                    ))
                    leg_seq += 1

                # Transit Leg 1
                inter1 = get_intermediate_stops(conn, raw["trip1_id"], raw["seq1"], raw["seq2"])
                mode1_disp = get_mode_name(m1["mode_name"], lang)
                legs.append(JourneyLeg(
                    leg_sequence=leg_seq,
                    leg_type="TRANSIT",
                    mode=m1["mode_name"],
                    agency_id=m1["agency_id"],
                    agency_name=get_agency_name(m1["agency_id"], lang),
                    route_id=m1["route_id"],
                    route_short_name=m1["route_short_name"],
                    route_long_name=m1["route_long_name"],
                    trip_id=raw["trip1_id"],
                    departure_stop_id=raw["orig_stop_id"],
                    departure_stop_name=m1["orig_name"],
                    departure_time=sec_to_time(raw["dep1_sec"]),
                    departure_coords=Coordinate(lat=m1["orig_lat"], lon=m1["orig_lon"]),
                    arrival_stop_id=raw["xfer1_stop_id"],
                    arrival_stop_name=m1["xfer1_name"],
                    arrival_time=sec_to_time(raw["arr1_sec"]),
                    arrival_coords=Coordinate(lat=m1["xfer1_lat"], lon=m1["xfer1_lon"]),
                    duration_minutes=round((raw["arr1_sec"] - raw["dep1_sec"]) / 60.0, 1),
                    stops_count=raw["seq2"] - raw["seq1"],
                    intermediate_stops=inter1,
                    instruction=get_text(
                        lang, "board",
                        mode=mode1_disp,
                        route=m1["route_short_name"],
                        route_long=m1["route_long_name"]
                    ),
                    is_live=False,
                ))
                leg_seq += 1

                # Transfer Walk Leg (if transfer stops differ or > 15m)
                xw_m = raw["xfer_walk_dist"]
                xw_s = raw["xfer_walk_sec"]
                if raw["xfer1_stop_id"] != raw["xfer2_stop_id"] or xw_m > 15.0:
                    legs.append(JourneyLeg(
                        leg_sequence=leg_seq,
                        leg_type="WALK",
                        mode="Walk",
                        departure_stop_id=raw["xfer1_stop_id"],
                        departure_stop_name=m1["xfer1_name"],
                        departure_time=sec_to_time(raw["arr1_sec"]),
                        departure_coords=Coordinate(lat=m1["xfer1_lat"], lon=m1["xfer1_lon"]),
                        arrival_stop_id=raw["xfer2_stop_id"],
                        arrival_stop_name=m2["xfer2_name"],
                        arrival_time=sec_to_time(raw["arr1_sec"] + xw_s),
                        arrival_coords=Coordinate(lat=m2["xfer2_lat"], lon=m2["xfer2_lon"]),
                        duration_minutes=round(xw_s / 60.0, 1),
                        distance_meters=xw_m,
                        instruction=get_text(
                            lang, "transfer_walk",
                            distance=int(xw_m),
                            stop_name=m2["xfer2_name"],
                            minutes=max(1, int(xw_s / 60.0))
                        ),
                        is_live=False,
                    ))
                    leg_seq += 1

                # Transit Leg 2
                inter2 = get_intermediate_stops(conn, raw["trip2_id"], raw["seq3"], raw["seq4"])
                mode2_disp = get_mode_name(m2["mode_name"], lang)
                legs.append(JourneyLeg(
                    leg_sequence=leg_seq,
                    leg_type="TRANSIT",
                    mode=m2["mode_name"],
                    agency_id=m2["agency_id"],
                    agency_name=get_agency_name(m2["agency_id"], lang),
                    route_id=m2["route_id"],
                    route_short_name=m2["route_short_name"],
                    route_long_name=m2["route_long_name"],
                    trip_id=raw["trip2_id"],
                    departure_stop_id=raw["xfer2_stop_id"],
                    departure_stop_name=m2["xfer2_name"],
                    departure_time=sec_to_time(raw["dep2_sec"]),
                    departure_coords=Coordinate(lat=m2["xfer2_lat"], lon=m2["xfer2_lon"]),
                    arrival_stop_id=raw["dest_stop_id"],
                    arrival_stop_name=m2["dest_name"],
                    arrival_time=sec_to_time(raw["arr2_sec"]),
                    arrival_coords=Coordinate(lat=m2["dest_lat"], lon=m2["dest_lon"]),
                    duration_minutes=round((raw["arr2_sec"] - raw["dep2_sec"]) / 60.0, 1),
                    stops_count=raw["seq4"] - raw["seq3"],
                    intermediate_stops=inter2,
                    instruction=get_text(
                        lang, "board",
                        mode=mode2_disp,
                        route=m2["route_short_name"],
                        route_long=m2["route_long_name"]
                    ),
                    is_live=False,
                ))
                leg_seq += 1

                # Walk 2
                w2_m = tres["dest_walk_dist_m"]
                w2_s = tres["dest_walk_dur_sec"]
                if w2_m > 15.0 and dest_pt:
                    legs.append(JourneyLeg(
                        leg_sequence=leg_seq,
                        leg_type="WALK",
                        mode="Walk",
                        departure_stop_id=raw["dest_stop_id"],
                        departure_stop_name=m2["dest_name"],
                        departure_time=sec_to_time(raw["arr2_sec"]),
                        departure_coords=Coordinate(lat=m2["dest_lat"], lon=m2["dest_lon"]),
                        arrival_stop_id="DESTINATION",
                        arrival_stop_name=dest_resolved_name,
                        arrival_time=sec_to_time(raw["arr2_sec"] + w2_s),
                        arrival_coords=Coordinate(lat=dest_pt["lat"], lon=dest_pt["lon"]),
                        duration_minutes=round(w2_s / 60.0, 1),
                        distance_meters=w2_m,
                        instruction=get_text(
                            lang, "walk_destination",
                            distance=int(w2_m),
                            minutes=max(1, int(w2_s / 60.0))
                        ),
                        is_live=False,
                    ))

                # Ranking: Duration + 12 min transfer penalty + walk penalty
                first_dep = dep_sec if (w1_m > 15.0 and orig_pt) else raw["dep1_sec"]
                last_arr = (raw["arr2_sec"] + w2_s) if (w2_m > 15.0 and dest_pt) else raw["arr2_sec"]
                t_dur_min = round((last_arr - first_dep) / 60.0, 1)
                t_walk_m = w1_m + xw_m + w2_m
                r_score = t_dur_min + 12.0 + (t_walk_m / 60.0) * 1.2

                summary = get_text(
                    lang, "journey_summary_transfer",
                    mode1=mode1_disp,
                    route1=m1["route_short_name"],
                    transfer_stop=m1["xfer1_name"],
                    mode2=mode2_disp,
                    route2=m2["route_short_name"],
                    destination=m2["dest_name"]
                )

                journey_options.append(JourneyOption(
                    journey_id=f"transfer-1-{t_idx}",
                    summary=summary,
                    departure_time=sec_to_time(first_dep),
                    arrival_time=sec_to_time(last_arr),
                    total_duration_minutes=t_dur_min,
                    total_walking_distance_m=round(t_walk_m, 1),
                    transfers_count=1,
                    ranking_score=round(r_score, 2),
                    legs=legs,
                    is_live=False,
                    primary_mode=f"{m1['mode_name']} + {m2['mode_name']}",
                    primary_route=f"{m1['route_short_name']} -> {m2['route_short_name']}",
                    boarding_stop=m1["orig_name"],
                    destination_stop=m2["dest_name"],
                    fare=None,
                    data_notice="Scheduled timetable data (GTFS static). Real-time GPS unavailable.",
                ))
                t_idx += 1

        # Sort all options by ranking_score
        journey_options.sort(key=lambda j: j.ranking_score)

        if not journey_options:
            no_route_msg = get_text(
                lang, "no_route_found",
                source=orig_resolved_name,
                destination=dest_resolved_name,
                time=dep_time_str
            )
            return JourneyPlanResponse(
                status="no_route_found",
                language=lang,
                departure_time=dep_time_str,
                service_date=date_formatted,
                source_resolved=orig_resolved_name,
                destination_resolved=dest_resolved_name,
                direct_journeys_found=0,
                transfer_journeys_found=0,
                data_notice=get_disclaimer(lang),
                error_details=no_route_msg,
                suggestions=[
                    "Check if there are earlier departures or search for a morning/daytime departure.",
                    "Increase max_walk_distance_m to find more candidate stops in the vicinity.",
                    "Allow 1 or 2 transfers if direct routes are unavailable.",
                    "Verify if the chosen date corresponds to regular operating days.",
                ]
            )

        return JourneyPlanResponse(
            status="success",
            language=lang,
            departure_time=dep_time_str,
            service_date=date_formatted,
            source_resolved=orig_resolved_name,
            destination_resolved=dest_resolved_name,
            direct_journeys_found=len(direct_results),
            transfer_journeys_found=transfer_results_count,
            data_notice=get_disclaimer(lang),
            journeys=journey_options[:settings.MAX_JOURNEY_RESULTS],
        )
