"""
Database service and connection manager for Kural Transit Engine.
"""

import os
import sqlite3
from typing import Dict, Any, Generator
from contextlib import contextmanager
from app.config import settings
from scripts.init_db import init_database


def get_db_connection() -> sqlite3.Connection:
    """Get a tuned SQLite connection."""
    ensure_database_initialized()
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def ensure_database_initialized():
    """Ensure database exists; if not, build it from GTFS."""
    if not os.path.exists(settings.DB_PATH):
        print(f"[Database] {settings.DB_PATH} not found. Building from GTFS files...")
        init_database(settings.DB_PATH, force=False)


def get_database_stats() -> Dict[str, Any]:
    """Retrieve summary counts and metadata from transit_engine.db."""
    with get_db() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM agencies")
        agencies_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM routes")
        routes_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM routes WHERE active_trips_count > 0")
        active_routes_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM trips")
        trips_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM stops")
        stops_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM stops WHERE is_active = 1")
        active_stops_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM stop_times")
        stop_times_count = cur.fetchone()[0]
        
        cur.execute("SELECT agency_id, agency_name FROM agencies")
        agencies = [dict(row) for row in cur.fetchall()]
        
        cur.execute("""
            SELECT agency_id, mode_name, COUNT(*) as count 
            FROM routes 
            GROUP BY agency_id, mode_name
        """)
        routes_by_agency = [dict(row) for row in cur.fetchall()]
        
        cur.execute("""
            SELECT service_id, start_date, end_date, 
                   (monday || tuesday || wednesday || thursday || friday || saturday || sunday) as days
            FROM calendar
        """)
        calendars = [dict(row) for row in cur.fetchall()]
        
    return {
        "agencies_count": agencies_count,
        "routes_count": routes_count,
        "active_routes_count": active_routes_count,
        "inactive_routes_count": routes_count - active_routes_count,
        "trips_count": trips_count,
        "stops_count": stops_count,
        "active_stops_count": active_stops_count,
        "stop_times_count": stop_times_count,
        "agencies": agencies,
        "routes_by_agency": routes_by_agency,
        "service_calendars": calendars,
    }

