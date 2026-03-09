"""
Freshservice Middleware API
───────────────────────────
Entry point for the FastAPI application.

This middleware sits between Power Automate / Copilot Studio
and the Freshservice ITSM REST API.

To run locally:
    uvicorn app.main:app --reload --port 8000

Swagger UI (auto-generated API docs):
    http://localhost:8000/docs

ReDoc:
    http://localhost:8000/redoc
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.manager import user_router, manager_router
from app.routes.tickets import router as tickets_router
from app.models.responses import HealthResponse
from app.config import get_settings


# ── App instance ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Freshservice Middleware API",
    description=(
        "A middleware layer between **Microsoft Copilot Studio / Power Automate** "
        "and the **Freshservice ITSM REST API**.\n\n"
        "All routes require the `x-api-key` header (your MIDDLEWARE_API_KEY from .env)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS (allow Power Automate / Azure to call this API) ──────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Tighten this in production to your Azure domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(tickets_router)
app.include_router(user_router)       # /users   — role detection
app.include_router(manager_router)  


# ── Health check (no auth required) ───────────────────────────────────────────
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Returns OK if the service is running. No auth required.",
)
async def health_check():
    """
    Power Automate and Azure can ping this to confirm the service is alive.
    No x-api-key header needed for this endpoint.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="freshservice-middleware",
        env=settings.app_env,
    )


# ── Root redirect to docs ──────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
