"""
Kural Transit Engine - FastAPI Application Entry Point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.database import ensure_database_initialized
from app.services.geocoding import init_spatial_index
from app.api.routes import (
    health_router,
    stops_router,
    routes_router,
    journey_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to warm up database and spatial KDTree index."""
    print(f"[{settings.PROJECT_NAME}] Starting up...")
    ensure_database_initialized()
    init_spatial_index()
    print(f"[{settings.PROJECT_NAME}] Ready for requests.")
    yield
    print(f"[{settings.PROJECT_NAME}] Shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend/dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(journey_router)
app.include_router(stops_router)
app.include_router(routes_router)


@app.get("/", tags=["Root"])
def root():
    return {
        "engine": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "documentation": "/docs",
        "endpoints": {
            "health": "GET /health",
            "journey_plan": "POST /api/journey/plan",
            "kural_tool_search_journey": "POST /api/kural/tools/search_journey",
            "stops_search": "GET /api/stops/search",
            "routes_search": "GET /api/routes/search",
        },
        "disclaimer": "All arrival and departure times are scheduled timetable data. Real-time GPS/live vehicle locations are not available.",
    }


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)

