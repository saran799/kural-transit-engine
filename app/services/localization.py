"""
Localization service for Kural Transit Engine (English & Tamil).
"""

from typing import Dict, Any

TRANSLATIONS = {
    "en": {
        "agency_names": {
            "69": "Metropolitan Transport Corporation (MTC)",
            "CMRL": "Chennai Metro Rail Limited (CMRL)",
            "SR": "Southern Railway (SR Suburban)",
        },
        "modes": {
            "Bus": "Bus",
            "Metro": "Metro",
            "Suburban Rail": "Suburban Rail",
            "Walk": "Walk",
        },
        "instructions": {
            "walk_origin": "Walk {distance}m to {stop_name} (approx {minutes} min)",
            "board": "Board {mode} {route} ({route_long}) towards destination",
            "intermediate": "Pass through {count} stops",
            "alight": "Alight at {stop_name}",
            "transfer_walk": "Walk {distance}m to transfer stop {stop_name} (approx {minutes} min)",
            "walk_destination": "Walk {distance}m to final destination (approx {minutes} min)",
        },
        "disclaimer": "Scheduled timetable data only. Real-time live vehicle arrivals are not available.",
        "journey_summary_direct": "Direct {mode} {route} from {origin} to {destination}",
        "journey_summary_transfer": "{mode1} {route1} to {transfer_stop}, then {mode2} {route2} to {destination}",
        "no_route_found": "No valid scheduled transit journey found between {source} and {destination} after {time}.",
        "error_unresolved_stop": "Could not locate or resolve stop: '{query}'. Please check the stop name or use coordinates.",
        "error_out_of_bounds": "The requested coordinates ({lat}, {lon}) are outside the Chennai transit coverage area.",
    },
    "ta": {
        "agency_names": {
            "69": "மாநகரப் போக்குவரத்துக் கழகம் (MTC)",
            "CMRL": "சென்னை மெட்ரோ ரயில் (CMRL)",
            "SR": "தெற்கு ரயில்வே புறநகர் சேவை (SR)",
        },
        "modes": {
            "Bus": "பேருந்து",
            "Metro": "மெட்ரோ ரயில்",
            "Suburban Rail": "புறநகர் ரயில்",
            "Walk": "நடைபயணம்",
        },
        "instructions": {
            "walk_origin": "{stop_name} நிறுத்தத்திற்கு {distance} மீ நடக்கவும் (சுமார் {minutes} நிமிடம்)",
            "board": "{route} ({route_long}) {mode}-இல் ஏறவும்",
            "intermediate": "{count} நிறுத்தங்கள் வழியே செல்லவும்",
            "alight": "{stop_name} நிறுத்தத்தில் இறங்கவும்",
            "transfer_walk": "மாற்று நிறுத்தம் {stop_name} வரை {distance} மீ நடக்கவும் (சுமார் {minutes} நிமிடம்)",
            "walk_destination": "சேருமிடம் வரை {distance} மீ நடக்கவும் (சுமார் {minutes} நிமிடம்)",
        },
        "disclaimer": "அட்டவணை அடிப்படையிலான நேரங்கள் மட்டுமே. நிகழ்நேர ஜிபிஎஸ் அல்லது நேரலை வாகன கண்காணிப்பு தகவல் இல்லை.",
        "journey_summary_direct": "{origin} முதல் {destination} வரை நேரடி {mode} {route}",
        "journey_summary_transfer": "{transfer_stop} வரை {route1} {mode1}, பின்னர் {destination} வரை {route2} {mode2}",
        "no_route_found": "{source} முதல் {destination} வரை {time}-க்கு பிறகு திட்டமிடப்பட்ட பயணங்கள் எதுவும் கிடைக்கவில்லை.",
        "error_unresolved_stop": "நிறுத்தத்தை கண்டுபிடிக்க முடியவில்லை: '{query}'. பெயர் அல்லது ஆயங்களை சரிபார்க்கவும்.",
        "error_out_of_bounds": "கொடுக்கப்பட்ட ஆயங்கள் ({lat}, {lon}) சென்னை போக்குவரத்து எல்லைக்கு வெளியே உள்ளன.",
    },
}


def get_text(lang: str, key: str, **kwargs) -> str:
    """Retrieve localized string with format substitutions, supporting flat or nested instruction keys."""
    lang_code = "ta" if lang and lang.lower().startswith("ta") else "en"
    dict_for_lang = TRANSLATIONS.get(lang_code, TRANSLATIONS["en"])
    
    # Check top-level
    text = dict_for_lang.get(key)
    # Check under 'instructions' if not found at top-level
    if text is None and "instructions" in dict_for_lang:
        text = dict_for_lang["instructions"].get(key)
    
    # Fallback to English
    if text is None:
        text = TRANSLATIONS["en"].get(key)
        if text is None and "instructions" in TRANSLATIONS["en"]:
            text = TRANSLATIONS["en"]["instructions"].get(key)
            
    if text is None:
        text = key

    if isinstance(text, str):
        return text.format(**kwargs) if kwargs else text
    return str(text)


def get_mode_name(mode: str, lang: str = "en") -> str:
    lang_code = "ta" if lang and lang.lower().startswith("ta") else "en"
    return TRANSLATIONS[lang_code]["modes"].get(mode, mode)


def get_agency_name(agency_id: str, lang: str = "en") -> str:
    lang_code = "ta" if lang and lang.lower().startswith("ta") else "en"
    return TRANSLATIONS[lang_code]["agency_names"].get(agency_id, agency_id)


def get_disclaimer(lang: str = "en") -> str:
    lang_code = "ta" if lang and lang.lower().startswith("ta") else "en"
    return TRANSLATIONS[lang_code]["disclaimer"]
