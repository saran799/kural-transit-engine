"""
Geocoding, spatial indexing, and stop resolution service for Kural Transit Engine.
"""

import math
import re
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from scipy.spatial import cKDTree
from app.services.database import get_db
from app.config import settings

# Global spatial index state
_kdtree: Optional[cKDTree] = None
_stops_data: List[Dict[str, Any]] = []
_stop_id_to_index: Dict[str, int] = {}

TAMIL_LOCALITY_MAP = {
    "பூந்தமல்லி": "Poonamallee",
    "போரூர்": "Porur",
    "கிண்டி": "Guindy",
    "தாம்பரம்": "Tambaram",
    "சென்ட்ரல்": "Central",
    "சென்னை சென்ட்ரல்": "Chennai Central",
    "எழும்பூர்": "Egmore",
    "கோயம்பேடு": "Koyambedu",
    "வடபழனி": "Vadapalani",
    "அடையாறு": "Adyar",
    "திருவான்மியூர்": "Thiruvanmiyur",
    "வேளச்சேரி": "Velachery",
    "ஆவடி": "Avadi",
    "அம்பத்தூர்": "Ambattur",
    "பிராட்வே": "Broadway",
    "தி.நகர்": "T Nagar",
    "தி நகர்": "T Nagar",
    "தியாகராய நகர்": "T Nagar",
    "அண்ணா நகர்": "Anna Nagar",
    "பல்லாவரம்": "Pallavaram",
    "குரோம்பேட்டை": "Chromepet",
    "பாரிமுனை": "Parrys",
    "மீனம்பாக்கம்": "Meenambakkam",
    "செங்குன்றம்": "Red Hills",
    "மாதவரம்": "Madhavaram",
    "சோழிங்கநல்லூர்": "Sholinganallur",
    "திருவொற்றியூர்": "Tiruvottiyur",
}

COMMON_LOCALITY_SUFFIXES = [
    r"\bbus\s+terminus\b",
    r"\bbus\s+stand\b",
    r"\bbus\s+stop\b",
    r"\brailway\s+station\b",
    r"\bmetro\s+station\b",
    r"\bterminus\b",
    r"\broundana\b",
    r"\broundtana\b",
    r"\bjunction\b",
    r"\bcircle\b",
    r"\bdepot\b",
    r"\bstation\b",
    r"\bjn\b",
    r"\bstop\b",
    r"\bstand\b",
    # Tanglish particles
    r"\b(la|le|ku|kku|lendhu|lerundhu|ilirunthu)\b",
]


def clean_locality_query(query: str) -> str:
    """Normalize a place or stop name by stripping punctuation, Tamil script or common noise words."""
    cleaned = query.strip()
    
    # Check Tamil script dictionary
    if cleaned in TAMIL_LOCALITY_MAP:
        return TAMIL_LOCALITY_MAP[cleaned]
    for tam, eng in TAMIL_LOCALITY_MAP.items():
        if tam in cleaned:
            cleaned = cleaned.replace(tam, eng)

    # Clean punctuation e.g. T. Nagar -> T Nagar
    cleaned = cleaned.replace(".", " ")
    for pattern in COMMON_LOCALITY_SUFFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned



def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points on Earth in meters."""
    R = 6371000.0  # Earth's radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def init_spatial_index():
    """Build in-memory KDTree for all stops for fast nearest-neighbor lookups."""
    global _kdtree, _stops_data, _stop_id_to_index
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT stop_id, stop_name, stop_lat, stop_lon, location_type, 
                   parent_station, agency_id, is_active
            FROM stops
        """)
        rows = cur.fetchall()
        
    _stops_data = [dict(row) for row in rows]
    _stop_id_to_index = {s["stop_id"]: idx for idx, s in enumerate(_stops_data)}
    
    if _stops_data:
        coords = np.radians([[s["stop_lat"], s["stop_lon"]] for s in _stops_data])
        _kdtree = cKDTree(coords)
    print(f"[Geocoding] Initialized spatial KDTree with {len(_stops_data)} stops.")


def get_spatial_tree() -> Tuple[cKDTree, List[Dict[str, Any]]]:
    """Ensure spatial KDTree is ready and return tree + stops list."""
    global _kdtree, _stops_data
    if _kdtree is None or not _stops_data:
        init_spatial_index()
    return _kdtree, _stops_data


def find_nearby_stops(
    lat: float,
    lon: float,
    radius_m: float = 1000.0,
    active_only: bool = True,
    limit: int = 30
) -> List[Dict[str, Any]]:
    """Find stops within radius_m meters of given coordinates."""
    tree, stops = get_spatial_tree()
    pt = np.radians([lat, lon])
    r_rad = radius_m / 6371000.0
    
    indices = tree.query_ball_point(pt, r_rad)
    results = []
    
    for idx in indices:
        s = stops[idx]
        if active_only and s["is_active"] != 1 and s["location_type"] != 1:
            continue
        dist = haversine_distance(lat, lon, s["stop_lat"], s["stop_lon"])
        walk_sec = max(30, int(dist / settings.DEFAULT_WALK_SPEED_MPS))
        results.append({
            **s,
            "distance_m": round(dist, 1),
            "walk_duration_sec": walk_sec,
            "walk_duration_min": round(walk_sec / 60.0, 1),
        })
        
    results.sort(key=lambda x: x["distance_m"])
    return results[:limit]


def get_stop_by_id(stop_id: str) -> Optional[Dict[str, Any]]:
    """Get stop record by stop_id."""
    _, stops = get_spatial_tree()
    idx = _stop_id_to_index.get(stop_id)
    if idx is not None:
        return stops[idx]
    return None


def resolve_location(
    location: Union[str, Dict[str, float]],
    radius_m: float = 1000.0,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, float]], str]:
    """
    Resolve location input (coordinates, stop_id, or name query) to candidate stops.
    Returns: (candidate_stops, original_point_coords_or_none, location_name)
    """
    ensure_spatial_index = get_spatial_tree
    ensure_spatial_index()

    # Case 1: Coordinate dictionary or model {"lat": ..., "lon": ...} / Coordinate(lat=..., lon=...)
    if hasattr(location, "lat") and hasattr(location, "lon"):
        lat, lon = float(location.lat), float(location.lon)
        nearby = find_nearby_stops(lat, lon, radius_m=radius_m, active_only=True)
        point = {"lat": lat, "lon": lon}
        name = f"Location ({lat:.4f}, {lon:.4f})"
        return nearby, point, name

    if isinstance(location, dict) and "lat" in location and "lon" in location:
        lat, lon = float(location["lat"]), float(location["lon"])
        nearby = find_nearby_stops(lat, lon, radius_m=radius_m, active_only=True)
        point = {"lat": lat, "lon": lon}
        name = f"Location ({lat:.4f}, {lon:.4f})"
        return nearby, point, name

    query_str = str(location).strip()

    # Case 2: Exact Stop ID match
    direct_stop = get_stop_by_id(query_str)
    if direct_stop:
        # If it's a station with location_type = 1 (parent station), resolve child platforms
        if direct_stop["location_type"] == 1:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT stop_id, stop_name, stop_lat, stop_lon, location_type, 
                           parent_station, agency_id, is_active
                    FROM stops
                    WHERE parent_station = ? AND is_active = 1
                """, (query_str,))
                children = [dict(r) for r in cur.fetchall()]
            
            if children:
                # Add walking distance from station center
                for c in children:
                    d = haversine_distance(direct_stop["stop_lat"], direct_stop["stop_lon"], c["stop_lat"], c["stop_lon"])
                    c["distance_m"] = round(d, 1)
                    c["walk_duration_sec"] = max(30, int(d / settings.DEFAULT_WALK_SPEED_MPS))
                    c["walk_duration_min"] = round(c["walk_duration_sec"] / 60.0, 1)
                point = {"lat": direct_stop["stop_lat"], "lon": direct_stop["stop_lon"]}
                return children, point, direct_stop["stop_name"]

        # Regular active stop: return it with 0m walk distance
        dist_record = {
            **direct_stop,
            "distance_m": 0.0,
            "walk_duration_sec": 0,
            "walk_duration_min": 0.0,
        }
        point = {"lat": direct_stop["stop_lat"], "lon": direct_stop["stop_lon"]}
        return [dist_record], point, direct_stop["stop_name"]

    # Case 3: Stop name search (text query)
    cleaned_query = clean_locality_query(query_str)
    search_terms = [query_str]
    if cleaned_query.lower() != query_str.lower() and len(cleaned_query) >= 3:
        search_terms.append(cleaned_query)

    matches = []
    with get_db() as conn:
        cur = conn.cursor()
        for term in search_terms:
            # Search with prioritized relevance: exact match > prefix match > word match > substring
            cur.execute("""
                SELECT stop_id, stop_name, stop_lat, stop_lon, location_type, 
                       parent_station, agency_id, is_active
                FROM stops
                WHERE stop_name LIKE ?
                ORDER BY 
                    (CASE 
                        WHEN LOWER(stop_name) = LOWER(?) THEN 1
                        WHEN LOWER(stop_name) LIKE LOWER(? || ' %') THEN 2
                        WHEN LOWER(stop_name) LIKE LOWER(? || '%') THEN 3
                        WHEN LOWER(stop_name) LIKE LOWER('% ' || ? || '%') THEN 4
                        ELSE 5
                     END) ASC,
                    is_active DESC, location_type ASC
                LIMIT 20
            """, (f"%{term}%", term, term, term, term))
            found_rows = [dict(r) for r in cur.fetchall()]
            if found_rows:
                matches = found_rows
                break

    if not matches:
        return [], None, query_str

    # Select primary match
    primary = matches[0]
    p_lat, p_lon = primary["stop_lat"], primary["stop_lon"]
    point = {"lat": p_lat, "lon": p_lon}

    # Find all stops within 800m of this primary matching place/station
    nearby = find_nearby_stops(p_lat, p_lon, radius_m=max(radius_m, 800.0), active_only=True)
    
    # If any nearby stop has the exact name of the query (e.g. 'Porur' or 'Poonamallee'),
    # treat it as a direct terminal stop with 0m walk penalty
    for s in nearby:
        if s["stop_name"].strip().lower() == query_str.lower():
            s["distance_m"] = 0.0
            s["walk_duration_sec"] = 0
            s["walk_duration_min"] = 0.0

    # Ensure primary match itself is at top if active
    if primary["is_active"] == 1:
        if not any(s["stop_id"] == primary["stop_id"] for s in nearby):
            nearby.insert(0, {
                **primary,
                "distance_m": 0.0,
                "walk_duration_sec": 0,
                "walk_duration_min": 0.0,
            })
        else:
            # Reorder so exact matching stops come first
            nearby.sort(key=lambda x: (0 if x["stop_name"].strip().lower() == query_str.lower() else 1, x.get("distance_m", 9999)))

    return nearby, point, primary["stop_name"]
