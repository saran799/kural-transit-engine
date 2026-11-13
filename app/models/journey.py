"""
Journey planning request and response models for Kural Transit Engine.
"""

from typing import Optional, List, Union
from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    lat: float
    lon: float


class JourneyPlanRequest(BaseModel):
    source: Union[str, Coordinate] = Field(
        ...,
        description="Source stop ID (e.g. 'MTC-9440'), stop name (e.g. 'Poonamallee'), or coordinates {lat, lon}",
        examples=["Poonamallee", {"lat": 13.05087, "lon": 80.09372}]
    )
    destination: Union[str, Coordinate] = Field(
        ...,
        description="Destination stop ID (e.g. 'MTC-5738'), stop name (e.g. 'Porur'), or coordinates {lat, lon}",
        examples=["Porur", {"lat": 13.03465, "lon": 80.15653}]
    )
    departure_time: Optional[str] = Field(
        default=None,
        description="Departure time in HH:MM:SS or HH:MM format. Defaults to current or early morning time."
    )
    date: Optional[str] = Field(
        default=None,
        description="Service date in YYYY-MM-DD format. Defaults to current date."
    )
    language: str = Field(
        default="en",
        description="Response language: 'en' for English, 'ta' for Tamil (தமிழ்)"
    )
    max_transfers: int = Field(
        default=2,
        ge=0,
        le=3,
        description="Maximum transfers allowed (0 = direct journeys only, 1 = up to 1 transfer, etc.)"
    )
    max_walk_distance_m: float = Field(
        default=1000.0,
        ge=100.0,
        le=3000.0,
        description="Maximum walking distance in meters to access transit stops or between transfers."
    )
    route_filter: Optional[str] = Field(
        default=None,
        description="Optional filter by route short name (e.g. 'S23', '29A', '549')"
    )
    modes: Optional[List[str]] = Field(
        default=None,
        description="Optional list of transit modes to allow: ['Bus', 'Metro', 'Suburban Rail']"
    )
    strict_calendar: bool = Field(
        default=False,
        description="Whether to strictly enforce calendar date range limits or allow day-of-week active schedules."
    )


class IntermediateStop(BaseModel):
    stop_sequence: int
    stop_id: str
    stop_name: str
    arrival_time: str
    stop_lat: Optional[float] = None
    stop_lon: Optional[float] = None


class JourneyLeg(BaseModel):
    leg_sequence: int
    leg_type: str  # 'WALK' or 'TRANSIT'
    mode: str      # 'Walk', 'Bus', 'Metro', 'Suburban Rail'
    agency_id: Optional[str] = None
    agency_name: Optional[str] = None
    route_id: Optional[str] = None
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    trip_id: Optional[str] = None
    departure_stop_id: str
    departure_stop_name: str
    departure_time: str
    departure_coords: Optional[Coordinate] = None
    arrival_stop_id: str
    arrival_stop_name: str
    arrival_time: str
    arrival_coords: Optional[Coordinate] = None
    duration_minutes: float
    distance_meters: Optional[float] = None
    stops_count: Optional[int] = None
    intermediate_stops: List[IntermediateStop] = []
    instruction: str
    is_live: bool = False
    schedule_source: str = "GTFS_STATIC_SCHEDULE"


class JourneyOption(BaseModel):
    journey_id: str
    summary: str
    departure_time: str
    arrival_time: str
    total_duration_minutes: float
    total_walking_distance_m: float
    transfers_count: int
    ranking_score: float
    legs: List[JourneyLeg]
    is_live: bool = False


class JourneyPlanResponse(BaseModel):
    status: str  # 'success', 'no_route_found', 'error'
    language: str
    departure_time: str
    service_date: str
    source_resolved: str
    destination_resolved: str
    direct_journeys_found: int
    transfer_journeys_found: int
    data_notice: str
    journeys: List[JourneyOption] = []
    error_details: Optional[str] = None
    suggestions: Optional[List[str]] = None


class KuralToolJourneyRequest(BaseModel):
    """
    Request schema matching ElevenLabs / n8n conversational agent tool definitions.
    Accepts origin, destination, mode, language, call_id, and standard routing options.
    """
    origin: Optional[str] = Field(
        default=None,
        description="Origin stop name or place (e.g. 'Poonamallee')",
        examples=["Poonamallee"]
    )
    source: Optional[Union[str, Coordinate]] = Field(
        default=None,
        description="Alternative field for origin: stop ID, stop name, or coordinates {lat, lon}"
    )
    destination: Union[str, Coordinate] = Field(
        ...,
        description="Destination stop ID, stop name (e.g. 'Porur'), or coordinates {lat, lon}",
        examples=["Porur"]
    )
    departure_time: Optional[str] = Field(
        default=None,
        description="Optional departure time in HH:MM format (or HH:MM:SS)",
        examples=["10:00", "08:30:00"]
    )
    date: Optional[str] = Field(
        default=None,
        description="Service date in YYYY-MM-DD format"
    )
    mode: Optional[str] = Field(
        default=None,
        description="Preferred transit mode, e.g. 'Bus', 'Metro', or 'Suburban Rail'"
    )
    modes: Optional[List[str]] = Field(
        default=None,
        description="Optional list of transit modes to allow"
    )
    language: str = Field(
        default="en",
        description="Response language: 'en' for English, 'ta' for Tamil (தமிழ்)"
    )
    max_transfers: int = Field(
        default=2,
        ge=0,
        le=3,
        description="Maximum transfers allowed (0 = direct only, 1 or 2 = transfers allowed)"
    )
    call_id: Optional[str] = Field(
        default=None,
        description="ElevenLabs or telephony conversation / call ID"
    )


class KuralToolJourneyResponse(BaseModel):
    """
    Response schema matching ElevenLabs conversational agent tool expectations.
    Includes voice-optimized spoken_response, options summary, and found flag.
    """
    found: bool = Field(..., description="Whether at least one valid journey was found")
    spoken_response: str = Field(..., description="Natural language spoken response formatted for TTS voice delivery")
    total_options: int = Field(..., description="Total number of journey options found")
    options: List[JourneyOption] = Field(default=[], description="List of journey options with legs, stops, and schedules")
    raw_plan: Optional[JourneyPlanResponse] = Field(default=None, description="Complete underlying journey plan data")
    call_id: Optional[str] = Field(default=None, description="Echoed call identifier")


