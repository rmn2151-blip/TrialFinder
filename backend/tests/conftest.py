"""
Shared pytest configuration.

Environment is set here, before any application module is imported, so every
test run is deterministic regardless of the developer's local .env.
"""

import os

# Rate limiting off: tests create many accounts quickly and would otherwise
# trip the production limits and fail for unrelated reasons.
os.environ["RATE_LIMIT_ENABLED"] = "false"

# Never treat a test run as production.
os.environ["ENVIRONMENT"] = "development"

# Deterministic signing key, long enough to satisfy the HS256 length check.
os.environ.setdefault(
    "JWT_SECRET", "test-secret-long-enough-for-hs256-rfc7518-compliance"
)

# No outbound network calls from the test suite.
os.environ["MOCK_SEARCH"] = "true"
os.environ.pop("RESEND_API_KEY", None)
os.environ.pop("SMTP_HOST", None)
