"""
Journey planning API endpoints for Kural Transit Engine.
"""

from fastapi import APIRouter, HTTPException, status
from app.models.journey import (
    JourneyPlanRequest,
    JourneyPlanResponse,
    KuralToolJourneyRequest,
    KuralToolJourneyResponse,
)
from app.services.journey_planner import plan_journey

router = APIRouter(tags=["Journey Planning"])


def _generate_spoken_response(plan_res: JourneyPlanResponse, language: str) -> str:
    """Generate a concise, clear spoken response for ElevenLabs text-to-speech."""
    is_ta = (language or "").lower() == "ta"
    
    if plan_res.status != "success" or not plan_res.journeys:
        if is_ta:
            return f"மன்னிக்கவும், {plan_res.source_resolved} முதல் {plan_res.destination_resolved} வரை எந்த பொதுப் போக்குவரத்து வழியும் கிடைக்கவில்லை. மாற்று நேரம் அல்லது வேறு நிறுத்தத்தை முயற்சிக்கவும்."
        return f"Sorry, no transit journeys were found from {plan_res.source_resolved} to {plan_res.destination_resolved} around {plan_res.departure_time}. Please try a different departure time or nearby stops."
    
    best = plan_res.journeys[0]
    total_min = int(round(best.total_duration_minutes))
    
    if is_ta:
        msg = f"{plan_res.source_resolved} முதல் {plan_res.destination_resolved} வரை {len(plan_res.journeys)} பயண வழிகள் உள்ளன. "
        msg += f"முதல் வழி: {best.summary}, புறப்படும் நேரம் {best.departure_time}, சேரும் நேரம் {best.arrival_time}, பயண நேரம் சுமார் {total_min} நிமிடங்கள்."
        return msg
    else:
        msg = f"Found {len(plan_res.journeys)} journey options from {plan_res.source_resolved} to {plan_res.destination_resolved}. "
        msg += f"Recommended option: {best.summary}, departing at {best.departure_time} and arriving at {best.arrival_time}. Total journey time is approximately {total_min} minutes."
        return msg


@router.post("/api/journey/plan", response_model=JourneyPlanResponse)
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


@router.post(
    "/api/kural/tools/search_journey",
    response_model=KuralToolJourneyResponse,
    tags=["Kural Tools", "Journey Planning"],
    summary="Search journey tool for ElevenLabs / voice assistant"
)
def search_journey_tool(request: KuralToolJourneyRequest):
    """
    Tool endpoint for ElevenLabs / n8n conversational voice agent.
    
    Accepts:
    - origin or source (stop name, ID, or coords)
    - destination (stop name, ID, or coords)
    - mode (optional: 'Bus', 'Metro', 'Suburban Rail')
    - language ('en' or 'ta')
    - call_id (telephony / conversation identifier)
    
    Returns voice-ready spoken_response, found status, and structured options.
    """
    source_val = request.origin if request.origin is not None else request.source
    if not source_val:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'origin' or 'source' must be provided."
        )
    
    modes_val = request.modes
    if not modes_val and request.mode:
        modes_val = [request.mode]
        
    core_request = JourneyPlanRequest(
        source=source_val,
        destination=request.destination,
        departure_time=request.departure_time,
        date=request.date,
        language=request.language,
        max_transfers=request.max_transfers,
        modes=modes_val,
    )
    
    plan_res = plan_journey(core_request)
    found = plan_res.status == "success" and len(plan_res.journeys) > 0
    spoken = _generate_spoken_response(plan_res, request.language)
    
    return KuralToolJourneyResponse(
        found=found,
        spoken_response=spoken,
        total_options=len(plan_res.journeys),
        options=plan_res.journeys,
        raw_plan=plan_res,
        call_id=request.call_id,
    )


