from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.database import init_db
from app.routers import benchmarks, pitching, hitting, defense, team, predictions, divergences, editorials

settings = get_settings()

app = FastAPI(
    title="CubsStats API",
    description="Cubs sabermetrics ML dashboard — dynamic benchmarks, divergence detection, win predictions",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    """Health check — verifies API is up and DB is reachable."""
    from sqlalchemy import text
    from app.models.database import SessionLocal
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "app": "cubsstats", "database": db_status}


# Register routers
app.include_router(benchmarks.router, prefix="/api/benchmarks", tags=["benchmarks"])
app.include_router(pitching.router, prefix="/api/pitching", tags=["pitching"])
app.include_router(hitting.router, prefix="/api/hitting", tags=["hitting"])
app.include_router(defense.router, prefix="/api/defense", tags=["defense"])
app.include_router(team.router, prefix="/api/team", tags=["team"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(divergences.router, prefix="/api/divergences", tags=["divergences"])
app.include_router(editorials.router, prefix="/api/editorials", tags=["editorials"])
