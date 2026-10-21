"""FastAPI application bootstrap and database lifecycle."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import settings
from server.database import init_db
from server.routers import agent, data, plans, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the configured SQLite schema before serving requests."""
    init_db(settings.flowpilot_db_path)
    yield


app = FastAPI(title="FlowPilot", lifespan=lifespan)
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.flowpilot_cors_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In production / single-process mode, serve built frontend assets if present
from pathlib import Path
from fastapi.staticfiles import StaticFiles

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

