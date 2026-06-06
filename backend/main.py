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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

load_dotenv()

from db.database import init_db
from routers.auth import router as auth_router
from routers.match import limiter, router as match_router
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
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

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
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server and any deployed frontend origin
# ---------------------------------------------------------------------------

_allowed_origins = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:3000",   # CRA dev server (fallback)
    "http://127.0.0.1:5173",
]

# Allow a production domain set via env var
_frontend_url = os.getenv("FRONTEND_URL")
if _frontend_url:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# #region agent log
@app.middleware("http")
async def _debug_request_log(request, call_next):
    """Log method + path for CORS and routing diagnosis."""
    import json
    import time

    response = await call_next(request)
    if request.method in ("DELETE", "PUT", "OPTIONS") or request.url.path.startswith("/api/match"):
        try:
            with open(
                "/Users/ruhaninagda/Documents/Claude/Projects/TrialFinder/.cursor/debug-1e06ce.log",
                "a",
            ) as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "1e06ce",
                            "hypothesisId": "B",
                            "location": "main.py:_debug_request_log",
                            "message": "request completed",
                            "data": {
                                "method": request.method,
                                "path": request.url.path,
                                "status": response.status_code,
                                "origin": request.headers.get("origin"),
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except OSError:
            pass
    return response


# #endregion

# ---------------------------------------------------------------------------
# Rate limiting middleware
# ---------------------------------------------------------------------------

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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

# ---------------------------------------------------------------------------
# Startup log
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup():
    init_db()  # create watchlist tables if they don't exist
    mock_mode = os.getenv("MOCK_LINKUP", "false").lower() == "true"
    logger.info(f"TrialFinder API started — MOCK_LINKUP={mock_mode}")
    if not os.getenv("LINKUP_API_KEY"):
        logger.warning("LINKUP_API_KEY not set — set MOCK_LINKUP=true for dev mode")
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set")
