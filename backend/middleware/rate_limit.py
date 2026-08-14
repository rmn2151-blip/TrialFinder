"""
Single shared rate limiter.

slowapi resolves limits through `app.state.limiter`, so every router must use
the same Limiter instance. Separate instances per router silently fail to
share state, which is how endpoints end up unlimited without anyone noticing.

Behind a proxy (Railway, Render, Vercel) the socket peer is the proxy, so we
read the client IP from X-Forwarded-For and fall back to the socket address.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

# Trust the proxy's forwarded header only when we know we are behind one.
_TRUST_PROXY = os.getenv("TRUST_PROXY_HEADERS", "true").lower() == "true"


def client_key(request: Request) -> str:
    if _TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Left-most entry is the original client.
            return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_key)
