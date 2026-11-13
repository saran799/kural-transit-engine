"""
Application configuration for Kural Transit Engine.
"""

import os
from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    PROJECT_NAME: str = "Kural Transit Engine"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Multimodal Public-Transport Journey Planning API for Chennai"
    
    BASE_DIR: str = BASE_DIR
    DB_PATH: str = os.path.join(BASE_DIR, "transit_engine.db")
    
    # Journey planner defaults
    DEFAULT_WALK_SPEED_MPS: float = 1.2  # ~4.3 km/h
    DEFAULT_MAX_WALK_RADIUS_M: float = 1000.0  # 1 km
    DEFAULT_TRANSFER_BUFFER_SEC: int = 180  # 3 minutes min transfer time
    DEFAULT_MAX_TRANSFERS: int = 2
    MAX_JOURNEY_RESULTS: int = 5
    
    # Agency labels
    AGENCY_NAMES: dict = {
        "69": "Metropolitan Transport Corporation (MTC)",
        "CMRL": "Chennai Metro Rail Limited (CMRL)",
        "SR": "Southern Railway (SR Suburban)",
    }


settings = Settings()

