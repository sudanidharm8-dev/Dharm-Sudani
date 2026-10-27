"""
main.py — FairShift Guardian application entry point.

Registers all routers, configures CORS (restricted origins),
attaches the rate-limiter, and serves the frontend HTML pages.
Works on both local uvicorn AND Vercel serverless.
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Absolute path — works on local, Docker, AND Vercel
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _html(filename: str) -> HTMLResponse:
    """Read an HTML file and return it as an HTMLResponse."""
    path = FRONTEND_DIR / filename
    content = path.read_text(encoding="utf-8")
    return HTMLResponse(content=content)


from backend.config import settings
from backend.routes import checkin, dashboard, mood, near_miss, wage_proof

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.API_RATE_LIMIT])

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FairShift Guardian",
    description=(
        "AI-powered workforce fairness platform for construction sites and college campuses. "
        "Aligned with UN SDG 8 — Decent Work and Economic Growth."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "*",          # Open for Vercel preview; lock down in Cloud Run production
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(checkin.router,    prefix="/api", tags=["Check-In"])
app.include_router(near_miss.router,  prefix="/api", tags=["Safety"])
app.include_router(mood.router,       prefix="/api", tags=["Mood"])
app.include_router(wage_proof.router, prefix="/api", tags=["Wages"])
app.include_router(dashboard.router,  prefix="/api", tags=["Dashboard"])

# ---------------------------------------------------------------------------
# Page routes — reads HTML files directly (works on Vercel + Cloud Run)
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
@app.get("/login.html", include_in_schema=False)
def login_page() -> HTMLResponse:
    return _html("login.html")

@app.get("/worker", include_in_schema=False)
@app.get("/worker.html", include_in_schema=False)
def worker_page() -> HTMLResponse:
    return _html("worker.html")

@app.get("/worker-login", include_in_schema=False)
@app.get("/worker-login.html", include_in_schema=False)
def worker_login_page() -> HTMLResponse:
    return _html("worker-login.html")

@app.get("/admin", include_in_schema=False)
@app.get("/admin.html", include_in_schema=False)
def admin_page() -> HTMLResponse:
    return _html("admin.html")

@app.get("/admin-login", include_in_schema=False)
@app.get("/admin-login.html", include_in_schema=False)
def admin_login_page() -> HTMLResponse:
    return _html("admin-login.html")

# ---------------------------------------------------------------------------
# Health — Cloud Run liveness probe
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": settings.APP_VERSION})


logger.info("FairShift Guardian v%s started (env=%s)", settings.APP_VERSION, settings.APP_ENV)
