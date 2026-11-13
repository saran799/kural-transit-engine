"""
Journey planning API endpoints for Kural Transit Engine.
"""

from fastapi import APIRouter, HTTPException, status
from app.models.journey import JourneyPlanRequest, JourneyPlanResponse
from app.services.journey_planner import plan_journey

router = APIRouter(prefix="/api/journey", tags=["Journey Planning"])


@router.post("/plan", response_model=JourneyPlanResponse)
def post_plan_journey(request: JourneyPlanRequest):
    """
    Plan multimodal public transport journeys across Chennai.
    
    Accepts:
    - source & destination (stop IDs, stop names, or coordinates {lat, lon})
    - departure_time (HH:MM:SS or HH:MM)
    - date (YYYY-MM-DD)
    - language ('en' for English, 'ta' for Tamil)
    - max_transfers (0 for direct only, 1 or 2 for transfers)
    - route_filter (e.g. 'S23')
    
    Returns chronological journey legs with stop sequences, scheduled times, and transparent data notices.
    """
    response = plan_journey(request)
    return response

