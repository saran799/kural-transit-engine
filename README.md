# Kural Transit Engine (குறள் போக்குவரத்து இயங்குதளம்)
### Reliable Multimodal Public-Transport Journey Planning API for Chennai

Kural Transit Engine is a high-performance, multimodal journey planning backend built with **FastAPI**, **SQLite**, **Pandas**, **NumPy**, **SciPy**, and **Pydantic**. It ingests the official General Transit Feed Specification (GTFS) dataset for the Chennai metropolitan region and provides schedule-aware journey planning across **Metropolitan Transport Corporation (MTC) buses**, **Chennai Metro Rail Limited (CMRL) metro lines**, and **Southern Railway (SR) suburban/MRTS trains**.

---

## 1. Dataset Inspection & GTFS Findings

A comprehensive audit was performed on all original GTFS files before writing code. **No original GTFS files were modified or deleted.**

### Agency Coverage & Mode Distinction
The dataset spans three public transportation providers in Chennai:
1. **Metropolitan Transport Corporation (MTC)** (`agency_id: 69`):
   - **Mode**: City and suburban buses (`route_type: 3`)
   - **Total Routes**: 4,611 routes in `routes.txt`
   - **Active Routes with scheduled trips**: 3,934 routes
   - **Inactive Routes**: 677 routes in `routes.txt` have **0 trips** in `trips.txt`. They cannot be assumed to be operating.
   - **Scheduled Trips**: 47,047 trips (46,973 `MTC-Regular`, 74 `MTC-HSC`)
   - **Stops**: 5,580 bus stops (5,477 visited in scheduled trips, 103 unvisited)

2. **Chennai Metro Rail Limited (CMRL)** (`agency_id: CMRL`):
   - **Mode**: Rapid Transit Metro (`route_type: 1`)
   - **Total Routes**: 28 routes (all 28 active with trips)
   - **Scheduled Trips**: 625 trips (service `CMRL-WD`)
   - **Stops**: 254 stop records (81 active platform stops, 173 station parents and entrance nodes)

3. **Southern Railway (SR Suburban & MRTS)** (`agency_id: SR`):
   - **Mode**: Suburban EMU Rail & MRTS (`route_type: 1` in dataset)
   - **Total Routes**: 763 routes (all 763 active with trips)
   - **Scheduled Trips**: 763 trips (`SRR-service_1111111`, `SRR-service_1111110`, `SRR-service_0000001`)
   - **Stops**: 708 stop records (144 active platform stops, 564 station parents and entrance nodes)

### Summary Statistics
| Metric | Count | Notes |
| :--- | :--- | :--- |
| **Agencies** | 3 | MTC, CMRL, Southern Railway |
| **Total Routes** | 5,402 | 4,725 active; 677 without scheduled trips |
| **Total Trips** | 48,435 | 47,047 MTC; 625 CMRL; 763 SR |
| **Total Stops** | 6,542 | 5,702 active; 840 station parents or entrance nodes |
| **Stop Times** | 1,389,081 | Scheduled arrival and departure records |
| **Walking Interchanges** | 12,759 | Spatial links computed within 300m for transfers |
| **GTFS Transfers** | 50 | Metro interchange rules from `transfers.txt` |

### Service Calendars & Validity Dates
- **MTC Regular & HSC**: `2024-05-01` to `2030-05-01` (Daily and Mon–Sat schedules; valid and active).
- **Southern Railway (SRR)**: `2025-08-06` to `2170-08-20` (Covers present day and future operating dates).
- **CMRL Metro (`CMRL-WD`)**: `2021-04-20` to `2021-12-31`. In the raw feed, CMRL's static calendar carries historical service dates. The engine supports both strict date validation (`strict_calendar: true`) and day-of-week active timetable mode (`strict_calendar: false`, default) so multimodal journeys incorporating Metro remain functional.

### Data-Quality Issues Discovered
1. **677 Inactive MTC Routes**: Present in `routes.txt` but absent in `trips.txt`. The engine tracks active trips per route and flags inactive routes.
2. **Missing `agency_id` for CMRL**: All 28 CMRL route records in `routes.txt` have an empty `agency_id`. The engine automatically normalizes these to `'CMRL'` based on the `CMRL-` route ID prefix.
3. **Midnight-Spanning Times (HH >= 24)**: 1,904 records in `stop_times.txt` have hours >= 24 (e.g. `24:05:00`). The engine converts all arrival and departure times into integer seconds from midnight, safely supporting overnight transit without parsing crashes.
4. **XSS Payload in Calendar**: `calendar.txt` contains a test injection payload (`MTC-'/><script>alert(1)</script>`). The database ingestion sanitizes and safely parametrizes all database records.
5. **Station Hierarchy vs. Platforms**: Vehicle trips visit platform stops (`location_type: 0`), while parent stations (`location_type: 1`) are not visited by vehicles. The engine's stop resolver expands parent stations to their active platform stops automatically.

---

## 2. First Validation: Poonamallee to Porur on Route S23

**Verification Question**: Does a direct S23 journey actually exist in the GTFS records?

**Answer**: **YES, it does.** A direct S23 journey exists in the GTFS records with 10 scheduled daily trips in each direction.

### Evidentiary Records
1. **Route Record** (`routes.txt`):
   ```csv
   route_id: MTC-18463
   route_short_name: S23
   route_long_name: Poonamallee TO Porur
   route_type: 3 (Bus)
   agency_id: 69 (MTC)
   ```
   *(The reverse route also exists: `MTC-18462`, `S23`, `Porur TO Poonamallee` with 10 trips).*

2. **Trip Records** (`trips.txt`):
   10 daily trips operate under `service_id: MTC-Regular`:
   - `MTC-70971`: Departure **06:55:00** → Arrival **07:13:00**
   - `MTC-70973`: Departure **08:40:00** → Arrival **08:58:00**
   - `MTC-70975`: Departure **10:20:00** → Arrival **10:38:00**
   - `MTC-70977`: Departure **11:50:00** → Arrival **12:08:00**
   - `MTC-70979`: Departure **13:10:00** → Arrival **13:28:00**
   - `MTC-70983`: Departure **15:50:00** → Arrival **16:08:00**
   - `MTC-70985`: Departure **17:20:00** → Arrival **17:38:00**
   - `MTC-70987`: Departure **19:00:00** → Arrival **19:18:00**
   - `MTC-70989`: Departure **20:40:00** → Arrival **20:58:00**
   - `MTC-70991`: Departure **22:05:00** → Arrival **22:23:00**

3. **Stop Sequence for Trip `MTC-70977` (11:50 AM departure)**:
   | Seq | Stop ID | Stop Name | Arrival | Departure |
   | :---: | :--- | :--- | :---: | :---: |
   | **1** | `MTC-9440` | **Poonamallee** (Boarding Stop) | 11:50:00 | **11:50:00** |
   | 2 | `MTC-9436` | Poonamallee Government Hospital | 11:52:00 | 11:52:00 |
   | 3 | `MTC-9428` | Kallarai | 11:54:00 | 11:54:00 |
   | 4 | `MTC-9392` | Karayanchavadi | 11:57:00 | 11:57:00 |
   | 5 | `MTC-10238` | Poonamallee Municipality Or Kumananchavadi | 11:58:00 | 11:58:00 |
   | 6 | `MTC-9364` | Vannan Kulam | 12:00:00 | 12:00:00 |
   | 7 | `MTC-5734` | Kattupakkam | 12:01:00 | 12:01:00 |
   | 8 | `MTC-5925` | Iyyappanthangal Bus Terminus | 12:05:00 | 12:05:00 |
   | 9 | `MTC-5737` | Ramachandra Hospital | 12:06:00 | 12:06:00 |
   | 10 | `MTC-9305` | Chettiyar Agaram | 12:07:00 | 12:07:00 |
   | **11** | `MTC-5738` | **Porur** (Alighting Stop) | **12:08:00** | 12:08:00 |
   | 12 | `MTC-9278` | Porur (Terminal Stop) | 12:09:00 | 12:09:00 |

   - **Travel Time**: Exactly **18 minutes**.
   - **Stops Traversed**: 10 stops.
   - **Walking Required**: 0 meters when boarding at Poonamallee and alighting at Porur.

---

## 3. Architecture & Engine Design

```
kural-transit-engine/
├── app/
│   ├── config.py                 # Application settings and tuning constants
│   ├── main.py                   # FastAPI application with CORS and lifespan events
│   ├── models/
│   │   ├── health.py             # Health check and telemetry response models
│   │   ├── stop.py               # Stop models and search schemas
│   │   ├── route.py              # Route models and search schemas
│   │   └── journey.py            # Journey planning request & response models
│   ├── services/
│   │   ├── database.py           # SQLite connection pool and statistics
│   │   ├── geocoding.py          # Spatial KDTree, haversine, and stop resolution
│   │   ├── localization.py       # English (en) and Tamil (ta) translations
│   │   ├── journey_planner.py    # Routing engine (direct & transfer search, ranking)
│   │   ├── stop_service.py       # Stop search and radius lookup
│   │   └── route_service.py      # Route search and mode filtering
├── scripts/
│   ├── init_db.py                # GTFS ingestion and index creation script
│   └── verify_api.py             # Direct engine test script
├── tests/
│   ├── test_health.py            # Tests GET /health
│   ├── test_stops.py             # Tests GET /api/stops/search
│   ├── test_routes.py            # Tests GET /api/routes/search
│   ├── test_validation_s23.py    # First validation tests for S23 Poonamallee to Porur
│   └── test_journey_planner.py   # Comprehensive journey tests (direct, transfer, Tamil, coords)
├── transit_engine.db             # Optimized SQLite database (built from GTFS)
├── requirements.txt
└── README.md
```

### Key Technical Decisions
1. **Integer Second Timetable Indexing**: Every scheduled time is converted into seconds from midnight. Time range queries (`departure_sec >= ?`) execute via integer B-Tree indexes in 1 to 3 milliseconds without string parsing overhead.
2. **Sub-millisecond Spatial KDTree**: Built over 6,542 stop coordinates using `scipy.spatial.cKDTree` in radians. Nearest-stop radius queries complete in 1 to 3 milliseconds.
3. **Multimodal Transfer Graph**: Interchanges between bus stops, metro stations, and suburban platforms within 300 meters are precomputed with walking distances and walking speeds (~1.2 m/s). Transfers respect arrival buffers (minimum 3 minutes) and layover limits (maximum 60 minutes).
4. **Intelligent Relevance Ranking**: Stops matching an exact name query (e.g. "Porur") are prioritized over substrings (e.g. "Thiruporur") so urban queries resolve accurately.
5. **Scheduled vs. Live Transparency**: Requirement 10 is strictly enforced. Every response and leg carries `is_live: false`, `schedule_source: "GTFS_STATIC_SCHEDULE"`, and an explicit disclaimer.

---

## 4. API Endpoints & Examples

### 1. Health Check
- **Endpoint**: `GET /health`
- **Description**: Returns GTFS dataset health, agency details, route counts, and static timetable notice.

**Example Request**:
```bash
curl -X GET "http://localhost:8000/health"
```

**Example Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "description": "Multimodal Public-Transport Journey Planning API for Chennai",
  "agencies_count": 3,
  "routes_count": 5402,
  "active_routes_count": 4725,
  "inactive_routes_count": 677,
  "trips_count": 48435,
  "stops_count": 6542,
  "active_stops_count": 5702,
  "stop_times_count": 1389081,
  "agencies": [
    {"agency_id": "69", "agency_name": "MTC"},
    {"agency_id": "CMRL", "agency_name": "Chennai Metro Rail Limited"},
    {"agency_id": "SR", "agency_name": "Southern Railway"}
  ],
  "routes_by_agency": [
    {"agency_id": "69", "mode_name": "Bus", "count": 4611},
    {"agency_id": "CMRL", "mode_name": "Metro", "count": 28},
    {"agency_id": "SR", "mode_name": "Suburban Rail", "count": 763}
  ],
  "data_source_notice": "Scheduled timetable static feed. Real-time live vehicle tracking is not available."
}
```

---

### 2. Stops Search
- **Endpoint**: `GET /api/stops/search`
- **Query Parameters**:
  - `query` (str, optional): Search by stop name or stop ID.
  - `lat`, `lon` (float, optional): Radial geographic search around coordinates.
  - `radius_m` (float, default 1000.0): Search radius in meters.
  - `agency_id` (str, optional): Filter by `'69'` (MTC), `'CMRL'`, or `'SR'`.
  - `active_only` (bool, default false): Filter only stops with active scheduled trips.
  - `limit` (int, default 20): Maximum results.

**Example Request**:
```bash
curl -X GET "http://localhost:8000/api/stops/search?query=Poonamallee&limit=3"
```

**Example Response**:
```json
{
  "total": 3,
  "query": "Poonamallee",
  "stops": [
    {
      "stop_id": "MTC-9440",
      "stop_name": "Poonamallee",
      "stop_lat": 13.05087,
      "stop_lon": 80.09372,
      "location_type": 0,
      "parent_station": null,
      "agency_id": "69",
      "is_active": 1,
      "distance_m": null,
      "walk_duration_min": null
    },
    {
      "stop_id": "MTC-9437",
      "stop_name": "Poonamallee",
      "stop_lat": 13.05041,
      "stop_lon": 80.09318,
      "location_type": 0,
      "parent_station": null,
      "agency_id": "69",
      "is_active": 1,
      "distance_m": null,
      "walk_duration_min": null
    },
    {
      "stop_id": "MTC-5821",
      "stop_name": "Poonamallee Bus Terminus",
      "stop_lat": 13.05183,
      "stop_lon": 80.09491,
      "location_type": 0,
      "parent_station": null,
      "agency_id": "69",
      "is_active": 1,
      "distance_m": null,
      "walk_duration_min": null
    }
  ]
}
```

---

### 3. Routes Search
- **Endpoint**: `GET /api/routes/search`
- **Query Parameters**:
  - `query` (str, optional): Route short name (e.g. `'S23'`) or long name.
  - `agency_id` (str, optional): Filter by agency (`'69'`, `'CMRL'`, `'SR'`).
  - `mode` (str, optional): Filter by mode (`'Bus'`, `'Metro'`, `'Suburban Rail'`).
  - `active_only` (bool, default false): Return only routes with scheduled trips.

**Example Request**:
```bash
curl -X GET "http://localhost:8000/api/routes/search?query=S23"
```

**Example Response**:
```json
{
  "total": 4,
  "query": "S23",
  "routes": [
    {
      "route_id": "MTC-18462",
      "route_short_name": "S23",
      "route_long_name": "Porur TO Poonamallee",
      "route_type": 3,
      "agency_id": "69",
      "agency_name": "Metropolitan Transport Corporation (MTC)",
      "mode_name": "Bus",
      "active_trips_count": 10
    },
    {
      "route_id": "MTC-18463",
      "route_short_name": "S23",
      "route_long_name": "Poonamallee TO Porur",
      "route_type": 3,
      "agency_id": "69",
      "agency_name": "Metropolitan Transport Corporation (MTC)",
      "mode_name": "Bus",
      "active_trips_count": 10
    },
    {
      "route_id": "MTC-15784",
      "route_short_name": "S23",
      "route_long_name": "Iyyappanthangal TO Porur",
      "route_type": 3,
      "agency_id": "69",
      "agency_name": "Metropolitan Transport Corporation (MTC)",
      "mode_name": "Bus",
      "active_trips_count": 2
    },
    {
      "route_id": "MTC-15785",
      "route_short_name": "S23",
      "route_long_name": "Porur TO Iyyappanthangal",
      "route_type": 3,
      "agency_id": "69",
      "agency_name": "Metropolitan Transport Corporation (MTC)",
      "mode_name": "Bus",
      "active_trips_count": 2
    }
  ]
}
```

---

### 4. Journey Plan (Direct S23 Journey)
- **Endpoint**: `POST /api/journey/plan`
- **Request Body**:
```json
{
  "source": "Poonamallee",
  "destination": "Porur",
  "departure_time": "11:00:00",
  "route_filter": "S23",
  "language": "en",
  "max_transfers": 0
}
```

**Response**:
```json
{
  "status": "success",
  "language": "en",
  "departure_time": "11:00:00",
  "service_date": "2026-11-13",
  "source_resolved": "Poonamallee",
  "destination_resolved": "Porur",
  "direct_journeys_found": 4,
  "transfer_journeys_found": 0,
  "data_notice": "Scheduled timetable data only. Real-time live vehicle arrivals are not available.",
  "journeys": [
    {
      "journey_id": "direct-1",
      "summary": "Direct Bus S23 from Poonamallee to Porur",
      "departure_time": "11:50:00",
      "arrival_time": "12:08:00",
      "total_duration_minutes": 18.0,
      "total_walking_distance_m": 0.0,
      "transfers_count": 0,
      "ranking_score": 18.0,
      "legs": [
        {
          "leg_sequence": 1,
          "leg_type": "TRANSIT",
          "mode": "Bus",
          "agency_id": "69",
          "agency_name": "Metropolitan Transport Corporation (MTC)",
          "route_id": "MTC-18463",
          "route_short_name": "S23",
          "route_long_name": "Poonamallee TO Porur",
          "trip_id": "MTC-70977",
          "departure_stop_id": "MTC-9440",
          "departure_stop_name": "Poonamallee",
          "departure_time": "11:50:00",
          "arrival_stop_id": "MTC-5738",
          "arrival_stop_name": "Porur",
          "arrival_time": "12:08:00",
          "duration_minutes": 18.0,
          "stops_count": 10,
          "instruction": "Board Bus S23 (Poonamallee TO Porur) towards destination",
          "is_live": false,
          "schedule_source": "GTFS_STATIC_SCHEDULE",
          "intermediate_stops": [
            {"stop_sequence": 2, "stop_id": "MTC-9436", "stop_name": "Poonamallee Government Hospital", "arrival_time": "11:52:00"},
            {"stop_sequence": 3, "stop_id": "MTC-9428", "stop_name": "Kallarai", "arrival_time": "11:54:00"},
            {"stop_sequence": 4, "stop_id": "MTC-9392", "stop_name": "Karayanchavadi", "arrival_time": "11:57:00"},
            {"stop_sequence": 5, "stop_id": "MTC-10238", "stop_name": "Poonamallee Municipality Or Kumananchavadi", "arrival_time": "11:58:00"},
            {"stop_sequence": 6, "stop_id": "MTC-9364", "stop_name": "Vannan Kulam", "arrival_time": "12:00:00"},
            {"stop_sequence": 7, "stop_id": "MTC-5734", "stop_name": "Kattupakkam", "arrival_time": "12:01:00"},
            {"stop_sequence": 8, "stop_id": "MTC-5925", "stop_name": "Iyyappanthangal Bus Terminus", "arrival_time": "12:05:00"},
            {"stop_sequence": 9, "stop_id": "MTC-5737", "stop_name": "Ramachandra Hospital", "arrival_time": "12:06:00"},
            {"stop_sequence": 10, "stop_id": "MTC-9305", "stop_name": "Chettiyar Agaram", "arrival_time": "12:07:00"}
          ]
        }
      ],
      "is_live": false
    }
  ]
}
```

---

### 5. Tamil Language Journey Plan (தமிழ்)
- **Request Body**:
```json
{
  "source": "Poonamallee",
  "destination": "Porur",
  "departure_time": "11:00:00",
  "route_filter": "S23",
  "language": "ta"
}
```

**Response Highlights**:
```json
{
  "status": "success",
  "language": "ta",
  "data_notice": "அட்டவணை அடிப்படையிலான நேரங்கள் மட்டுமே. நிகழ்நேர ஜிபிஎஸ் அல்லது நேரலை வாகன கண்காணிப்பு தகவல் இல்லை.",
  "journeys": [
    {
      "summary": "Poonamallee முதல் Porur வரை நேரடி பேருந்து S23",
      "legs": [
        {
          "instruction": "S23 (Poonamallee TO Porur) பேருந்து-இல் ஏறவும்",
          "mode": "பேருந்து",
          "is_live": false
        }
      ]
    }
  ]
}
```

---

### 6. Honest Error Reporting (No Route / Unknown Stop)
- **Request Body**:
```json
{
  "source": "NonExistentLocationChennai",
  "destination": "Porur",
  "departure_time": "10:00:00"
}
```

**Response**:
```json
{
  "status": "error",
  "language": "en",
  "error_details": "Could not locate or resolve stop: 'NonExistentLocationChennai'. Please check the stop name or use coordinates.",
  "suggestions": [
    "Check the stop spelling (e.g. 'Poonamallee', 'Porur', 'Guindy').",
    "Try passing coordinates {lat, lon} directly.",
    "Increase max_walk_distance_m if you are far from a transit stop."
  ],
  "journeys": []
}
```

---

## 5. Setup & Execution Instructions

### Prerequisites
- Python 3.10+ (Tested on Python 3.13)
- Required Python packages: `fastapi`, `uvicorn`, `pydantic`, `pandas`, `numpy`, `scipy`, `pytest`

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Ingest GTFS & Build Database (One-time, ~10 seconds)
```bash
python scripts/init_db.py
```
*Note: If `transit_engine.db` is already present, this step completes instantly.*

### Step 3: Run the Verification Script
```bash
python scripts/verify_api.py
```

### Step 4: Run the Automated Test Suite
```bash
python -m pytest -v
```
All 19 tests will execute and pass:
```
tests/test_health.py::test_health_endpoint PASSED
tests/test_journey_planner.py::test_direct_journey_general PASSED
tests/test_journey_planner.py::test_journey_with_coordinates PASSED
tests/test_journey_planner.py::test_transfer_journey_search PASSED
tests/test_journey_planner.py::test_tamil_localization PASSED
tests/test_journey_planner.py::test_honest_error_on_unknown_location PASSED
tests/test_journey_planner.py::test_scheduled_vs_live_distinction PASSED
tests/test_routes.py::test_search_route_s23 PASSED
tests/test_routes.py::test_search_metro_routes PASSED
tests/test_routes.py::test_search_suburban_routes PASSED
tests/test_routes.py::test_search_active_only PASSED
tests/test_stops.py::test_search_stops_by_name PASSED
tests/test_stops.py::test_search_stops_porur PASSED
tests/test_stops.py::test_search_stops_by_coordinates PASSED
tests/test_stops.py::test_search_stops_agency_filter PASSED
tests/test_validation_s23.py::test_gtfs_s23_route_evidence PASSED
tests/test_validation_s23.py::test_gtfs_s23_trips_evidence PASSED
tests/test_validation_s23.py::test_gtfs_s23_stop_times_sequence_evidence PASSED
tests/test_validation_s23.py::test_journey_planner_api_s23_validation PASSED
============================= 19 passed in 5.30s ==============================
```

### Step 5: Start the FastAPI Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation is available at: `http://localhost:8000/docs`

---

## 6. License & Attribution
- GTFS data published by **Ithu Ungal Soththu** under Open Data.
- Built for the **Kural Voice Agent & Transit Intelligence Ecosystem** for Chennai.

