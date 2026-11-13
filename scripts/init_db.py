"""
Database initialization script for Kural Transit Engine.
Parses raw GTFS static files and builds an optimized, indexed SQLite database (transit_engine.db).
"""

import os
import sys
import time
import csv
import sqlite3
from typing import Dict, Set
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "transit_engine.db")

AGENCY_MAP = {
    "69": "Metropolitan Transport Corporation (MTC)",
    "CMRL": "Chennai Metro Rail Limited (CMRL)",
    "SR": "Southern Railway (SR Suburban)",
}

AGENCY_MODE_MAP = {
    "69": ("Bus", 3),
    "CMRL": ("Metro", 1),
    "SR": ("Suburban Rail", 1),
}


def time_to_sec(t_str: str) -> int:
    """Convert GTFS HH:MM:SS string to seconds from midnight (handles HH >= 24)."""
    p = t_str.strip().split(":")
    return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])


def init_database(db_path: str = DB_PATH, force: bool = False) -> str:
    if os.path.exists(db_path) and not force:
        print(f"[InitDB] Database already exists at {db_path}. Skipping build (use force=True to rebuild).")
        return db_path

    if os.path.exists(db_path):
        os.remove(db_path)

    t_start = time.time()
    print(f"[InitDB] Starting GTFS ingestion into {db_path}...")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA synchronous = OFF")
    cur.execute("PRAGMA journal_mode = OFF")

    # 1. Agencies
    print("  -> Ingesting agency.txt...")
    cur.execute("""
    CREATE TABLE agencies (
        agency_id TEXT PRIMARY KEY,
        agency_name TEXT,
        agency_url TEXT,
        agency_timezone TEXT,
        agency_phone TEXT,
        agency_lang TEXT
    )
    """)
    agency_file = os.path.join(BASE_DIR, "agency.txt")
    with open(agency_file, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            cur.execute("INSERT INTO agencies VALUES (?,?,?,?,?,?)", (
                row["agency_id"],
                row["agency_name"],
                row.get("agency_url", ""),
                row.get("agency_timezone", "Asia/Kolkata"),
                row.get("agency_phone", ""),
                row.get("agency_lang", "en"),
            ))

    # 2. Calendar and Calendar Dates
    print("  -> Ingesting calendar.txt and calendar_dates.txt...")
    cur.execute("""
    CREATE TABLE calendar (
        service_id TEXT PRIMARY KEY,
        monday INTEGER,
        tuesday INTEGER,
        wednesday INTEGER,
        thursday INTEGER,
        friday INTEGER,
        saturday INTEGER,
        sunday INTEGER,
        start_date INTEGER,
        end_date INTEGER
    )
    """)
    cal_file = os.path.join(BASE_DIR, "calendar.txt")
    with open(cal_file, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            cur.execute("INSERT INTO calendar VALUES (?,?,?,?,?,?,?,?,?,?)", (
                row["service_id"],
                int(row["monday"]),
                int(row["tuesday"]),
                int(row["wednesday"]),
                int(row["thursday"]),
                int(row["friday"]),
                int(row["saturday"]),
                int(row["sunday"]),
                int(row["start_date"]),
                int(row["end_date"]),
            ))

    cur.execute("""
    CREATE TABLE calendar_dates (
        date INTEGER,
        service_id TEXT,
        exception_type INTEGER
    )
    """)
    cal_dates_file = os.path.join(BASE_DIR, "calendar_dates.txt")
    if os.path.exists(cal_dates_file):
        with open(cal_dates_file, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                cur.execute("INSERT INTO calendar_dates VALUES (?,?,?)", (
                    int(row["date"]),
                    row["service_id"],
                    int(row["exception_type"]),
                ))

    # 3. Trips
    print("  -> Ingesting trips.txt...")
    cur.execute("""
    CREATE TABLE trips (
        trip_id TEXT PRIMARY KEY,
        route_id TEXT,
        service_id TEXT,
        direction_id INTEGER,
        trip_headsign TEXT,
        shape_id TEXT
    )
    """)
    trips_per_route: Dict[str, int] = {}
    trips_file = os.path.join(BASE_DIR, "trips.txt")
    with open(trips_file, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        batch = []
        for row in r:
            r_id = row["route_id"]
            trips_per_route[r_id] = trips_per_route.get(r_id, 0) + 1
            dir_id = int(float(row["direction_id"])) if row.get("direction_id") else 0
            batch.append((
                row["trip_id"],
                r_id,
                row["service_id"],
                dir_id,
                row.get("trip_headsign", ""),
                row.get("shape_id", ""),
            ))
            if len(batch) >= 50000:
                cur.executemany("INSERT INTO trips VALUES (?,?,?,?,?,?)", batch)
                batch = []
        if batch:
            cur.executemany("INSERT INTO trips VALUES (?,?,?,?,?,?)", batch)

    # 4. Routes
    print("  -> Ingesting routes.txt (normalizing agency & mode)...")
    cur.execute("""
    CREATE TABLE routes (
        route_id TEXT PRIMARY KEY,
        route_short_name TEXT,
        route_long_name TEXT,
        route_type INTEGER,
        agency_id TEXT,
        agency_name TEXT,
        mode_name TEXT,
        active_trips_count INTEGER
    )
    """)
    routes_file = os.path.join(BASE_DIR, "routes.txt")
    with open(routes_file, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        batch = []
        for row in r:
            r_id = row["route_id"]
            a_id = row.get("agency_id", "").strip() if row.get("agency_id") else ""
            if not a_id:
                if r_id.startswith("CMRL"):
                    a_id = "CMRL"
                elif r_id.startswith("SRR") or r_id.startswith("SR"):
                    a_id = "SR"
                else:
                    a_id = "69"

            mode_name, def_rtype = AGENCY_MODE_MAP.get(a_id, ("Bus", 3))
            rtype = int(row["route_type"]) if row.get("route_type") else def_rtype
            a_name = AGENCY_MAP.get(a_id, a_id)
            trip_count = trips_per_route.get(r_id, 0)

            batch.append((
                r_id,
                row.get("route_short_name", "").strip(),
                row.get("route_long_name", "").strip(),
                rtype,
                a_id,
                a_name,
                mode_name,
                trip_count,
            ))
        cur.executemany("INSERT INTO routes VALUES (?,?,?,?,?,?,?,?)", batch)

    # 5. Stop Times
    print("  -> Ingesting stop_times.txt (converting times to integer seconds)...")
    cur.execute("""
    CREATE TABLE stop_times (
        trip_id TEXT,
        arrival_time TEXT,
        departure_time TEXT,
        arrival_sec INTEGER,
        departure_sec INTEGER,
        stop_id TEXT,
        stop_sequence INTEGER
    )
    """)
    used_stop_ids: Set[str] = set()
    stop_times_file = os.path.join(BASE_DIR, "stop_times.txt")
    with open(stop_times_file, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        batch = []
        for row in r:
            s_id = row["stop_id"]
            used_stop_ids.add(s_id)
            a_sec = time_to_sec(row["arrival_time"])
            d_sec = time_to_sec(row["departure_time"])
            seq = int(row["stop_sequence"])
            batch.append((
                row["trip_id"],
                row["arrival_time"],
                row["departure_time"],
                a_sec,
                d_sec,
                s_id,
                seq,
            ))
            if len(batch) >= 100000:
                cur.executemany("INSERT INTO stop_times VALUES (?,?,?,?,?,?,?)", batch)
                batch = []
        if batch:
            cur.executemany("INSERT INTO stop_times VALUES (?,?,?,?,?,?,?)", batch)

    # 6. Stops
    print("  -> Ingesting stops.txt...")
    cur.execute("""
    CREATE TABLE stops (
        stop_id TEXT PRIMARY KEY,
        stop_name TEXT,
        stop_lat REAL,
        stop_lon REAL,
        stop_desc TEXT,
        zone_id TEXT,
        location_type INTEGER,
        parent_station TEXT,
        platform_code TEXT,
        stop_code TEXT,
        agency_id TEXT,
        is_active INTEGER
    )
    """)
    stops_file = os.path.join(BASE_DIR, "stops.txt")
    stops_df = pd.read_csv(stops_file, low_memory=False)
    batch = []
    for _, row in stops_df.iterrows():
        s_id = str(row["stop_id"])
        if s_id.startswith("CMRL"):
            a_id = "CMRL"
        elif s_id.startswith("SRR"):
            a_id = "SR"
        else:
            a_id = "69"

        loc_type = int(row["location_type"]) if pd.notna(row["location_type"]) else 0
        p_station = str(row["parent_station"]) if pd.notna(row["parent_station"]) else None
        p_code = str(row["platform_code"]) if pd.notna(row["platform_code"]) else None
        s_code = str(row["stop_code"]) if pd.notna(row["stop_code"]) else None
        s_desc = str(row["stop_desc"]) if pd.notna(row["stop_desc"]) else None
        z_id = str(row["zone_id"]) if pd.notna(row["zone_id"]) else None
        is_act = 1 if s_id in used_stop_ids else 0

        batch.append((
            s_id,
            row["stop_name"].strip(),
            float(row["stop_lat"]),
            float(row["stop_lon"]),
            s_desc,
            z_id,
            loc_type,
            p_station,
            p_code,
            s_code,
            a_id,
            is_act,
        ))
    cur.executemany("INSERT INTO stops VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)

    # 7. Transfers & Walking Interchanges
    print("  -> Computing spatial walking transfers (< 300m) and GTFS transfers...")
    cur.execute("""
    CREATE TABLE transfers (
        from_stop_id TEXT,
        to_stop_id TEXT,
        walk_distance_m REAL,
        walk_duration_sec INTEGER,
        transfer_type INTEGER
    )
    """)
    transfers_file = os.path.join(BASE_DIR, "transfers.txt")
    if os.path.exists(transfers_file):
        with open(transfers_file, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                cur.execute("INSERT INTO transfers VALUES (?,?,?,?,?)", (
                    row["from_stop_id"],
                    row["to_stop_id"],
                    50.0,
                    60,
                    int(row.get("transfer_type", 0)),
                ))

    # KDTree spatial pairs
    coords = np.radians(stops_df[["stop_lat", "stop_lon"]].values)
    tree = cKDTree(coords)
    max_dist_m = 300.0
    r_rad = max_dist_m / 6371000.0
    pairs = tree.query_pairs(r_rad)

    def haversine_m(lat1, lon1, lat2, lon2):
        R = 6371000.0
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
        return 2.0 * R * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))

    walk_batch = []
    walk_speed_mps = 1.2  # ~4.3 km/h
    for i, j in pairs:
        s1 = stops_df.iloc[i]
        s2 = stops_df.iloc[j]
        id1, id2 = str(s1["stop_id"]), str(s2["stop_id"])
        d_m = haversine_m(s1["stop_lat"], s1["stop_lon"], s2["stop_lat"], s2["stop_lon"])
        dur_s = max(30, int(d_m / walk_speed_mps))
        walk_batch.append((id1, id2, round(d_m, 1), dur_s, 2))
        walk_batch.append((id2, id1, round(d_m, 1), dur_s, 2))
    cur.executemany("INSERT INTO transfers VALUES (?,?,?,?,?)", walk_batch)

    # 8. Create Indexes
    print("  -> Creating SQLite indexes for high-speed queries...")
    cur.execute("CREATE INDEX idx_st_stop_dep_sec ON stop_times(stop_id, departure_sec)")
    cur.execute("CREATE INDEX idx_st_trip_seq ON stop_times(trip_id, stop_sequence)")
    cur.execute("CREATE INDEX idx_st_trip_stop ON stop_times(trip_id, stop_id)")
    cur.execute("CREATE INDEX idx_trips_route ON trips(route_id)")
    cur.execute("CREATE INDEX idx_trips_service ON trips(service_id)")
    cur.execute("CREATE INDEX idx_stops_name ON stops(stop_name COLLATE NOCASE)")
    cur.execute("CREATE INDEX idx_stops_parent ON stops(parent_station)")
    cur.execute("CREATE INDEX idx_routes_short ON routes(route_short_name COLLATE NOCASE)")
    cur.execute("CREATE INDEX idx_transfers_from ON transfers(from_stop_id)")

    conn.commit()
    conn.close()

    elapsed = time.time() - t_start
    db_size = os.path.getsize(db_path) / (1024 * 1024)
    print(f"[InitDB] Successfully built {db_path} in {elapsed:.2f}s ({db_size:.2f} MB).")
    return db_path


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    init_database(force=force_flag)

