from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.config import settings
from server.database import init_db
from server.models import ErrorDetail, ErrorEnvelope
from server.routers import agent, data, plans, sessions, tasks, commitments, workspaces, task_drafts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the configured SQLite schema before serving requests."""
    init_db(settings.flowpilot_db_path)
    yield


app = FastAPI(title="FlowPilot", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return documented ErrorEnvelope for request validation errors."""
    errors = [{key: value for key, value in error.items() if key != "ctx"} for error in exc.errors()]
    envelope = ErrorEnvelope(error=ErrorDetail(code="VALIDATION_ERROR", message="Invalid request payload", details={"errors": errors}))
    from fastapi.encoders import jsonable_encoder
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=jsonable_encoder(envelope))


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Return documented ErrorEnvelope for HTTP status exceptions."""
    envelope = ErrorEnvelope(error=ErrorDetail(code=f"HTTP_{exc.status_code}", message=str(exc.detail)))
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Catch unexpected exceptions and return documented ErrorEnvelope without leaking raw traces."""
    envelope = ErrorEnvelope(error=ErrorDetail(code="INTERNAL_SERVER_ERROR", message="An unexpected server error occurred. Please try again."))
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=envelope.model_dump())
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(commitments.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(task_drafts.router, prefix="/api/v1")
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

