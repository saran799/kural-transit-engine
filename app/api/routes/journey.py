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
    """
    Generate natural, conversational spoken response for ElevenLabs voice delivery.
    Sounds like a helpful local transit assistant speaking in Tamil, Tanglish, or English.
    """
    is_ta = (language or "").lower().startswith("ta")
    src = plan_res.source_resolved
    dst = plan_res.destination_resolved
    dep_time = plan_res.departure_time

    if plan_res.status != "success" or not plan_res.journeys:
        if is_ta:
            return f"மன்னிக்கவும், {src}-லிருந்து {dst}-க்கு {dep_time}-க்கு திட்டமிடப்பட்ட பயணங்கள் எதுவும் கிடைக்கவில்லை. மாற்று நேரத்தையோ அல்லது அருகிலுள்ள வேறு நிறுத்தத்தையோ முயற்சிக்கவும்."
        return f"Sorry, no transit journeys were found from {src} to {dst} around {dep_time}. Please try a different departure time or nearby stops."

    best = plan_res.journeys[0]
    total_min = int(round(best.total_duration_minutes))

    # If it's a direct journey (0 transfers)
    if best.transfers_count == 0:
        route_num = best.primary_route or ""
        mode_str = best.primary_mode or "Bus"
        if is_ta:
            msg = f"உங்களுக்காக ஒரு நேரடி பொதுப்போக்குவரத்து வழித்தடம் கிடைத்துள்ளது. "
            if route_num:
                msg += f"{src}-லிருந்து வழித்தட எண் {route_num} பேருந்தில் ஏறி {dst} நிறுத்தத்தில் இறங்கலாம். "
            else:
                msg += f"{src}-லிருந்து ஏறி {dst} நிறுத்தத்தில் இறங்கலாம். "
            msg += f"புறப்படும் நேரம் {best.departure_time}, சேரும் நேரம் {best.arrival_time}. பயண நேரம் சுமார் {total_min} நிமிடங்கள்."
            if len(plan_res.journeys) > 1:
                msg += f" மேலும் {len(plan_res.journeys) - 1} மாற்று வழிகளும் உள்ளன."
            return msg
        else:
            msg = f"Found a direct {mode_str.lower()} service for your journey. "
            if route_num:
                msg += f"Board route {route_num} at {src} departing at {best.departure_time}, and alight at {dst} arriving at {best.arrival_time}. "
            else:
                msg += f"Depart from {src} at {best.departure_time} and arrive at {dst} at {best.arrival_time}. "
            msg += f"Total journey time is approximately {total_min} minutes."
            if len(plan_res.journeys) > 1:
                msg += f" There are {len(plan_res.journeys) - 1} other options available as well."
            return msg

    # If it's a transfer journey (1 or more transfers)
    else:
        transit_legs = [leg for leg in best.legs if leg.leg_type == "TRANSIT"]
        if is_ta:
            msg = f"{src}-லிருந்து {dst}-க்கு ஒரு இணைப்புப் பயணம் உள்ளது. "
            if len(transit_legs) >= 2:
                leg1, leg2 = transit_legs[0], transit_legs[1]
                msg += f"முதலில் {leg1.departure_stop_name}-லிருந்து {leg1.route_short_name or ''} {leg1.mode}-இல் ஏறி {leg1.arrival_stop_name}-ல் இறங்கவும். "
                msg += f"பின்னர் அங்கிருந்து {leg2.route_short_name or ''} {leg2.mode}-இல் ஏறி {leg2.arrival_stop_name}-க்கு செல்லலாம். "
            msg += f"புறப்படும் நேரம் {best.departure_time}. மொத்த பயண நேரம் சுமார் {total_min} நிமிடங்கள்."
            return msg
        else:
            msg = f"Found a connecting journey with {best.transfers_count} transfer. "
            if len(transit_legs) >= 2:
                leg1, leg2 = transit_legs[0], transit_legs[1]
                msg += f"First take {leg1.mode} {leg1.route_short_name or ''} from {leg1.departure_stop_name} to {leg1.arrival_stop_name}. "
                msg += f"Then transfer to {leg2.mode} {leg2.route_short_name or ''} to reach {leg2.arrival_stop_name}. "
            msg += f"Departing at {best.departure_time}. Total journey time is approximately {total_min} minutes."
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
        origin=plan_res.source_resolved or str(source_val),
        destination=plan_res.destination_resolved or str(request.destination),
        language=request.language or "ta",
        departure_time=plan_res.departure_time,
        total_options=len(plan_res.journeys),
        options=plan_res.journeys,
        raw_plan=plan_res,
        call_id=request.call_id,
    )


