"""
Stop search and lookup service for Kural Transit Engine.
"""

from typing import List, Dict, Any, Optional
from app.services.database import get_db
from app.services.geocoding import find_nearby_stops, get_stop_by_id
from app.models.stop import StopResponse, StopSearchResponse


def search_stops(
    query: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_m: float = 1000.0,
    agency_id: Optional[str] = None,
    active_only: bool = False,
    limit: int = 20,
) -> StopSearchResponse:
    """Search stops by query string or geographic radius."""
    limit = min(max(1, limit), 100)
    results: List[StopResponse] = []

    # 1. Geographic radius search if lat and lon provided
    if lat is not None and lon is not None:
        nearby = find_nearby_stops(lat, lon, radius_m=radius_m, active_only=active_only, limit=limit)
        if agency_id:
            nearby = [s for s in nearby if s["agency_id"].upper() == agency_id.upper()]
        
        for s in nearby[:limit]:
            results.append(StopResponse(
                stop_id=s["stop_id"],
                stop_name=s["stop_name"],
                stop_lat=s["stop_lat"],
                stop_lon=s["stop_lon"],
                location_type=s["location_type"],
                parent_station=s.get("parent_station"),
                agency_id=s["agency_id"],
                is_active=s["is_active"],
                distance_m=s.get("distance_m"),
                walk_duration_min=s.get("walk_duration_min"),
            ))
        return StopSearchResponse(total=len(results), query=f"geo({lat},{lon})", stops=results)

    # 2. Text / ID search
    if not query or query.strip() == "":
        query = "%"
    else:
        query = query.strip()

    sql = """
        SELECT stop_id, stop_name, stop_lat, stop_lon, location_type, 
               parent_station, agency_id, is_active
        FROM stops
        WHERE (stop_name LIKE ? OR stop_id = ?)
    """
    params: List[Any] = [f"%{query}%", query]

    if agency_id:
        sql += " AND UPPER(agency_id) = ?"
        params.append(agency_id.upper())

    if active_only:
        sql += " AND is_active = 1"

    sql += """
        ORDER BY 
            (CASE 
                WHEN LOWER(stop_name) = LOWER(?) THEN 1
                WHEN LOWER(stop_name) LIKE LOWER(? || ' %') THEN 2
                WHEN LOWER(stop_name) LIKE LOWER(? || '%') THEN 3
                WHEN LOWER(stop_name) LIKE LOWER('% ' || ? || '%') THEN 4
                ELSE 5
             END) ASC,
            is_active DESC, location_type ASC LIMIT ?
    """
    params.extend([query, query, query, query, limit])

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

    for r in rows:
        results.append(StopResponse(
            stop_id=r["stop_id"],
            stop_name=r["stop_name"],
            stop_lat=r["stop_lat"],
            stop_lon=r["stop_lon"],
            location_type=r["location_type"],
            parent_station=r["parent_station"],
            agency_id=r["agency_id"],
            is_active=r["is_active"],
        ))

    return StopSearchResponse(total=len(results), query=query, stops=results)
