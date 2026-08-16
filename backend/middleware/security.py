"""
Security middleware: response headers, request logging, and anomaly detection.

Adds three things the app was missing:
  1. Standard hardening headers on every response.
  2. Structured access logging with a request ID, so an incident can be traced.
  3. Lightweight in-memory anomaly detection that flags hosts producing an
     unusual rate of auth failures or 4xx/5xx responses.

The detector is intentionally simple and per-process. It is a tripwire for
logs and alerting, not a replacement for a WAF or a shared rate limiter.
"""

import logging
import os
import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("security")

_IS_PROD = os.getenv("ENVIRONMENT", "development").lower() in {
    "production",
    "prod",
    "staging",
}

# Anomaly thresholds, per IP, within the rolling window.
_WINDOW_SECONDS = 300
_AUTH_FAIL_THRESHOLD = 15
_ERROR_THRESHOLD = 50
_REQUEST_THRESHOLD = 300

# ip -> deque[(timestamp, kind)]
_events: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
_already_flagged: dict[str, float] = {}

_SENSITIVE_PATHS = ("/api/auth/",)

# Paths the platform probes internally over plain HTTP. Redirecting these,
# or rejecting their Host header, breaks the healthcheck and the deployment
# never becomes reachable.
_INFRA_PATHS = {"/api/health", "/health", "/healthz"}
_NO_HTTPS_REDIRECT_PATHS = _INFRA_PATHS

# Operator-configured public hostnames, e.g. "api.example.com".
_ALLOWED_HOSTS = [
    h.strip().replace("https://", "").replace("http://", "").rstrip("/").lower()
    for h in os.getenv("ALLOWED_HOSTS", "").split(",")
    if h.strip()
]


def _host_allowed(host_header: str) -> bool:
    """
    Validate the Host header against the configured allowlist.

    Supports exact matches and leading wildcards ("*.example.com"). The port
    is stripped first, since Host may arrive as "example.com:8080".
    """
    if not _ALLOWED_HOSTS:
        return True  # validation disabled

    host = (host_header or "").split(":")[0].strip().lower()
    if not host:
        return False

    for allowed in _ALLOWED_HOSTS:
        if allowed == "*":
            return True
        if allowed.startswith("*."):
            if host == allowed[2:] or host.endswith(allowed[1:]):
                return True
        elif host == allowed:
            return True
    return False


def _record(ip: str, kind: str) -> None:
    now = time.time()
    events = _events[ip]
    events.append((now, kind))

    cutoff = now - _WINDOW_SECONDS
    while events and events[0][0] < cutoff:
        events.popleft()

    auth_fails = sum(1 for _, k in events if k == "auth_fail")
    errors = sum(1 for _, k in events if k in ("client_error", "server_error"))
    total = len(events)

    reason = None
    if auth_fails >= _AUTH_FAIL_THRESHOLD:
        reason = f"{auth_fails} auth failures in {_WINDOW_SECONDS}s (possible credential stuffing)"
    elif errors >= _ERROR_THRESHOLD:
        reason = f"{errors} error responses in {_WINDOW_SECONDS}s (possible probing)"
    elif total >= _REQUEST_THRESHOLD:
        reason = f"{total} requests in {_WINDOW_SECONDS}s (unusual volume)"

    if reason:
        # Only re-alert once per window per IP so logs stay readable.
        last = _already_flagged.get(ip, 0)
        if now - last > _WINDOW_SECONDS:
            _already_flagged[ip] = now
            logger.warning("security.anomaly ip=%s detail=%s", ip, reason)


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        started = time.perf_counter()

        # Host header validation. Infrastructure paths are exempt because the
        # platform probes the container directly, so the Host is an internal
        # name or raw IP rather than the public domain. Rejecting those makes
        # every healthcheck fail with 400 while the app is running fine.
        if _IS_PROD and path not in _INFRA_PATHS:
            if not _host_allowed(request.headers.get("host", "")):
                logger.warning(
                    "security.bad_host ip=%s host=%r path=%s",
                    ip,
                    request.headers.get("host", "")[:100],
                    path,
                )
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid host header"}
                )

        # Enforce HTTPS in production. Platforms like Railway terminate TLS at
        # the edge and forward the original scheme in X-Forwarded-Proto.
        #
        # The health endpoint is exempt: the platform probes the container
        # directly over plain HTTP on the internal network, and healthcheckers
        # generally do not follow redirects, so a 301 here reads as a failed
        # check and the deploy never goes live.
        if _IS_PROD and path not in _NO_HTTPS_REDIRECT_PATHS:
            proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if proto == "http":
                https_url = str(request.url.replace(scheme="https"))
                return JSONResponse(
                    status_code=301,
                    content={"detail": "HTTPS required"},
                    headers={"Location": https_url},
                )

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            # Always log the full traceback server-side. In production the
            # client gets nothing useful, because leaking stack traces is an
            # information disclosure bug. In development we return the actual
            # error so it is debuggable without digging through the terminal.
            logger.exception(
                "request.unhandled_error id=%s ip=%s method=%s path=%s duration_ms=%.1f",
                request_id,
                ip,
                request.method,
                path,
                duration_ms,
            )
            _record(ip, "server_error")

            content = {
                "detail": "An internal error occurred.",
                "request_id": request_id,
            }
            if not _IS_PROD:
                content["detail"] = (
                    f"{type(exc).__name__}: {exc}"[:500]
                    or "An internal error occurred."
                )
                content["dev_note"] = (
                    "This detail is shown because ENVIRONMENT is not production."
                )
            return JSONResponse(status_code=500, content=content)

        duration_ms = (time.perf_counter() - started) * 1000
        status = response.status_code

        if status in (401, 403) and path.startswith(_SENSITIVE_PATHS):
            _record(ip, "auth_fail")
        elif 400 <= status < 500:
            _record(ip, "client_error")
        elif status >= 500:
            _record(ip, "server_error")
        else:
            _record(ip, "ok")

        level = logging.WARNING if status >= 400 else logging.INFO
        logger.log(
            level,
            "request id=%s ip=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            ip,
            request.method,
            path,
            status,
            duration_ms,
        )

        if duration_ms > 30_000:
            logger.warning(
                "request.slow id=%s path=%s duration_ms=%.1f", request_id, path, duration_ms
            )

        # --- Hardening headers ------------------------------------------------
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Request-ID"] = request_id
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        # This is a JSON API: it should never be rendered as a document, so a
        # restrictive CSP costs nothing and blocks a class of injection.
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        if _IS_PROD:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        # Never let a proxy or browser cache an authenticated API response.
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"

        return response
