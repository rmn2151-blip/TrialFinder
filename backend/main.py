"""
TrialFinder — FastAPI application entry point.

Run locally:
  uvicorn main:app --reload --port 8000

Deploy (Railway / Render):
  uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

load_dotenv()

from db.database import init_db
from middleware.security import SecurityMiddleware
from routers.auth import router as auth_router
from middleware.rate_limit import limiter
from routers.alerts import router as alerts_router
from routers.match import router as match_router
from routers.profiles import router as profiles_router
from routers.briefing import router as briefing_router
from routers.drug_intel import router as drug_intel_router
from routers.clarify import router as clarify_router
from routers.intake import router as intake_router
from routers.results import router as results_router
from routers.reputation import router as reputation_router
from routers.watchlist import router as watchlist_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

_IS_PROD = os.getenv("ENVIRONMENT", "development").lower() in {
    "production",
    "prod",
    "staging",
}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TrialFinder API",
    description=(
        "AI-powered clinical trial matching. "
        "Describe your condition and get a ranked shortlist of open trials "
        "with plain-English 'why this fits you' reasoning."
    ),
    version="1.0.0",
    # Interactive docs enumerate every endpoint and schema. Useful locally,
    # unnecessary attack surface in production.
    docs_url=None if _IS_PROD else "/docs",
    redoc_url=None if _IS_PROD else "/redoc",
    openapi_url=None if _IS_PROD else "/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server and any deployed frontend origin
# ---------------------------------------------------------------------------

# Local dev origins are only trusted outside production.
_allowed_origins: list[str] = []
if not _IS_PROD:
    _allowed_origins += [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

# Production frontend origin(s). FRONTEND_URL accepts a comma-separated list.
_frontend_url = os.getenv("FRONTEND_URL", "")
for origin in _frontend_url.split(","):
    origin = origin.strip().rstrip("/")
    if origin:
        _allowed_origins.append(origin)

# Vercel gives every preview deployment its own hostname. Allowing the whole
# *.vercel.app space is convenient but means any Vercel project could call
# this API from a browser, so it is restricted to non-production only.
# In production, list your exact domain(s) in FRONTEND_URL.
_origin_regex = None if _IS_PROD else r"https://.*\.vercel\.app"

if _IS_PROD and not _allowed_origins:
    logger.error(
        "FRONTEND_URL is not set in production. All cross-origin browser "
        "requests will be blocked until you set it."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    # Explicit allowlist rather than "*", so a malicious page cannot smuggle
    # arbitrary headers through a preflight.
    allow_headers=["Authorization", "Content-Type", "X-Cron-Token"],
    max_age=600,
)

# Security headers, request logging, HTTPS enforcement, anomaly detection.
app.add_middleware(SecurityMiddleware)

# Reject requests with a spoofed Host header in production.
_allowed_hosts = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
]
if _IS_PROD and _allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)


# ---------------------------------------------------------------------------
# Rate limiting middleware
# ---------------------------------------------------------------------------

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ---------------------------------------------------------------------------
# Global error handling
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch anything a route did not handle.

    Production returns a generic message so we never leak internals. Outside
    production the real exception is returned, which turns "The server hit an
    error" into an actionable message without needing the terminal.
    """
    from fastapi.responses import JSONResponse

    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "unhandled_exception id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )

    if _IS_PROD:
        detail = "An internal error occurred."
    else:
        detail = f"{type(exc).__name__}: {exc}"[:500]

    return JSONResponse(
        status_code=500, content={"detail": detail, "request_id": request_id}
    )

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(match_router)
app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(watchlist_router)
app.include_router(reputation_router)
app.include_router(drug_intel_router)
app.include_router(briefing_router)
app.include_router(intake_router)
app.include_router(clarify_router)
app.include_router(results_router)
app.include_router(alerts_router)

# ---------------------------------------------------------------------------
# Startup log
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup():
    init_db()  # create watchlist tables if they don't exist
    mock_mode = (
        os.getenv("MOCK_SEARCH", os.getenv("MOCK_LINKUP", "false")).lower() == "true"
    )
    logger.info("TrialFinder API started. MOCK_SEARCH=%s", mock_mode)
    logger.info("Trial data source: ClinicalTrials.gov API (free, no key needed)")
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set")
