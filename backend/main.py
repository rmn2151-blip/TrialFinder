"""
TrialFinder — FastAPI application entry point.

Run locally:
  uvicorn main:app --reload --port 8000

Deploy (Railway / Render):
  uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import logging
import os
import threading

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
#
# The platform's own healthcheck probes the container directly over the
# internal network, so its Host header is an internal name or IP rather than
# the public domain. If we only trust the public domain, every probe is
# rejected with 400 and the deploy is marked unhealthy even though the app is
# running perfectly. So we always allow the hosts the platform uses for
# internal traffic alongside whatever the operator configured.
_allowed_hosts = [
    h.strip().replace("https://", "").replace("http://", "").rstrip("/")
    for h in os.getenv("ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

# Host validation is handled inside SecurityMiddleware rather than by
# Starlette's TrustedHostMiddleware. Two reasons: the health endpoint has to
# stay reachable for probes that arrive with an internal hostname or a raw
# IP as the Host header, and Starlette only supports leading wildcards
# ("*.example.com"), which cannot express an internal IP range.
if _IS_PROD and _allowed_hosts:
    logger.info("Host header allowlist: %s (+ platform internal)", _allowed_hosts)
elif _IS_PROD:
    logger.info(
        "ALLOWED_HOSTS not set, so Host header validation is off. Set it to "
        "your API domain to enable it."
    )


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


# Set during startup so /api/health can report why the app is degraded
# instead of the container dying silently and the platform showing only
# "no deployment available".
STARTUP_STATE: dict = {"database": "unknown", "errors": []}


@app.on_event("startup")
async def startup():
    """
    Boot sequence, ordered so the log pinpoints any failure.

    Nothing here is allowed to crash the process. A container that exits
    during startup gives you a 404 page and no explanation; one that stays
    up and reports its own problems through /api/health is debuggable.
    """
    logger.info("=" * 60)
    logger.info("TrialFinder API starting")
    logger.info("  ENVIRONMENT   = %s", os.getenv("ENVIRONMENT", "development"))
    logger.info("  PORT          = %s", os.getenv("PORT", "(not set)"))
    logger.info("  LLM_PROVIDER  = %s", os.getenv("LLM_PROVIDER", "gemini"))
    logger.info("  MOCK_SEARCH   = %s", os.getenv("MOCK_SEARCH", "false"))

    # Report which required settings are present, without printing values.
    for name in ("JWT_SECRET", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL"):
        value = os.getenv(name, "")
        logger.info("  %-13s = %s", name, "set" if value else "NOT SET")

    # Email is the single most common thing to configure locally and forget to
    # set on the host, and its failure mode is silent: accounts are created,
    # no code ever arrives, and nothing looks broken.
    try:
        from services import email_service

        if email_service.is_configured():
            provider = "Resend" if os.getenv("RESEND_API_KEY") else "SMTP"
            logger.info(
                "  email         = %s, sending as %s",
                provider,
                os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER") or "(default)",
            )
        else:
            logger.error(
                "  email         = NOT CONFIGURED. Verification codes will NOT "
                "be emailed. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD "
                "and EMAIL_FROM (or RESEND_API_KEY) in this service's variables."
            )
            STARTUP_STATE["errors"].append(
                "Email is not configured, so verification codes cannot be sent."
            )
    except Exception as exc:
        logger.warning("  email         = check failed: %s", exc)

    if _IS_PROD and not os.getenv("JWT_SECRET", "").strip():
        msg = (
            "JWT_SECRET is not set but ENVIRONMENT=production. Authentication "
            "will fail. Set JWT_SECRET in the platform's variables."
        )
        logger.error(msg)
        STARTUP_STATE["errors"].append(msg)

    if _IS_PROD and not os.getenv("FRONTEND_URL", "").strip():
        logger.warning(
            "FRONTEND_URL is not set in production. Browser requests from your "
            "frontend will be blocked by CORS until you set it."
        )

    # Database init runs in a background thread rather than inline.
    #
    # Uvicorn does not accept connections until the startup event returns, so
    # a slow or unreachable Postgres would hold the port closed and every
    # platform healthcheck would fail with "service unavailable" while the
    # app looked fine in the logs. Starting the listener immediately and
    # connecting in the background keeps /api/health answerable throughout.
    def _init_database() -> None:
        try:
            init_db()
            STARTUP_STATE["database"] = "connected"
            logger.info("database = connected, tables ready")
        except Exception as exc:
            STARTUP_STATE["database"] = "failed"
            detail = f"{type(exc).__name__}: {exc}"[:300]
            STARTUP_STATE["errors"].append(f"Database init failed. {detail}")
            logger.error("database = FAILED. %s", detail)
            logger.error(
                "  If you just added Postgres, confirm DATABASE_URL is set on "
                "THIS service (Variables tab) and that the database finished "
                "provisioning, then redeploy."
            )

    STARTUP_STATE["database"] = "connecting"
    threading.Thread(target=_init_database, name="db-init", daemon=True).start()

    logger.info("Trial data: ClinicalTrials.gov API (free, no key required)")
    logger.info("Listener starting now; database connecting in background.")
    logger.info("Startup complete. Health: /api/health")
    logger.info("=" * 60)
