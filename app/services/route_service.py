"""
Route search and lookup service for Kural Transit Engine.
"""

from typing import List, Dict, Any, Optional
from app.services.database import get_db
from app.models.route import RouteResponse, RouteSearchResponse


def search_routes(
    query: Optional[str] = None,
    agency_id: Optional[str] = None,
    mode: Optional[str] = None,
    active_only: bool = False,
    limit: int = 20,
) -> RouteSearchResponse:
    """Search routes by short name, long name, or route_id."""
    limit = min(max(1, limit), 100)
    results: List[RouteResponse] = []

    sql = """
        SELECT route_id, route_short_name, route_long_name, route_type,
               agency_id, agency_name, mode_name, active_trips_count
        FROM routes
        WHERE 1=1
    """
    params: List[Any] = []

    if query and query.strip():
        q = query.strip()
        sql += " AND (route_short_name LIKE ? OR route_long_name LIKE ? OR route_id = ?)"
        params.extend([f"%{q}%", f"%{q}%", q])

    if agency_id and agency_id.strip():
        sql += " AND UPPER(agency_id) = ?"
        params.append(agency_id.strip().upper())

    if mode and mode.strip():
        sql += " AND UPPER(mode_name) = ?"
        params.append(mode.strip().upper())

    if active_only:
        sql += " AND active_trips_count > 0"

    sql += " ORDER BY active_trips_count DESC, route_short_name ASC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

    for r in rows:
        results.append(RouteResponse(
            route_id=r["route_id"],
            route_short_name=r["route_short_name"],
            route_long_name=r["route_long_name"],
            route_type=r["route_type"],
            agency_id=r["agency_id"],
            agency_name=r["agency_name"],
            mode_name=r["mode_name"],
            active_trips_count=r["active_trips_count"],
        ))

    return RouteSearchResponse(total=len(results), query=query, routes=results)

