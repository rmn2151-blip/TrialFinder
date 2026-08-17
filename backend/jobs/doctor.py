"""
Diagnostic tool. Tests every external dependency and reports exactly what
works and what does not, with a specific fix for each failure.

Run from the backend directory:

    python -m jobs.doctor
    python -m jobs.doctor --email you@example.com   # also sends a test email

Checks, in order:
  1. .env loading and required variables
  2. Database connection
  3. ClinicalTrials.gov API (trial data)
  4. LLM provider key (Gemini or Claude)
  5. Grounded web search
  6. Email delivery
"""

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

_failures: list[str] = []


def ok(msg: str) -> None:
    print(f"  {GREEN}PASS{RESET}  {msg}")


def fail(msg: str, fix: str) -> None:
    print(f"  {RED}FAIL{RESET}  {msg}")
    print(f"        {YELLOW}Fix:{RESET} {fix}")
    _failures.append(msg)


def warn(msg: str) -> None:
    print(f"  {YELLOW}WARN{RESET}  {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


def mask(value: str) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 12:
        return value[:3] + "..."
    return f"{value[:8]}...{value[-4:]} ({len(value)} chars)"


# ---------------------------------------------------------------------------
# 1. Environment
# ---------------------------------------------------------------------------


def check_env() -> None:
    section("1. Environment")

    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    gemini = os.getenv("GEMINI_API_KEY", "").strip()
    claude = os.getenv("ANTHROPIC_API_KEY", "").strip()
    sendgrid = os.getenv("SENDGRID_API_KEY", "").strip()
    resend = os.getenv("RESEND_API_KEY", "").strip()
    jwt = os.getenv("JWT_SECRET", "").strip()
    mock = os.getenv("MOCK_SEARCH", os.getenv("MOCK_LINKUP", "false")).lower()

    print(f"  {DIM}LLM_PROVIDER      = {provider}{RESET}")
    print(f"  {DIM}GEMINI_API_KEY    = {mask(gemini)}{RESET}")
    print(f"  {DIM}ANTHROPIC_API_KEY = {mask(claude)}{RESET}")
    print(f"  {DIM}SENDGRID_API_KEY  = {mask(sendgrid)}{RESET}")
    print(f"  {DIM}RESEND_API_KEY    = {mask(resend)}{RESET}")
    print(f"  {DIM}JWT_SECRET        = {mask(jwt)}{RESET}")
    print(f"  {DIM}MOCK_SEARCH       = {mock}{RESET}")
    print()

    if mock == "true":
        fail(
            "MOCK_SEARCH is true, so the app returns canned fixture data.",
            "Set MOCK_SEARCH=false in .env to get real trial results.",
        )
    else:
        ok("Mock mode is off, so real data will be used.")

    if not gemini and not claude:
        fail(
            "No LLM key set.",
            "Add GEMINI_API_KEY (https://aistudio.google.com/apikey) to .env",
        )
    else:
        ok("An LLM key is present.")

    if jwt and len(jwt) >= 32:
        ok("JWT_SECRET is set and long enough.")
    elif jwt:
        warn("JWT_SECRET is shorter than 32 bytes. Fine locally, weak in prod.")
    else:
        fail("JWT_SECRET is not set.", 'Run: python -c "import secrets; print(secrets.token_urlsafe(48))"')


# ---------------------------------------------------------------------------
# 2. Database
# ---------------------------------------------------------------------------


def check_database() -> None:
    section("2. Database")
    try:
        from sqlalchemy import text
        from db.database import DATABASE_URL, engine, init_db

        shown = DATABASE_URL
        if "@" in shown:  # hide credentials in a Postgres URL
            shown = shown.split("@")[0].split("//")[0] + "//***@" + shown.split("@")[-1]
        print(f"  {DIM}URL = {shown}{RESET}\n")

        init_db()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok("Connected and tables are ready.")

        from db.models import Account
        from sqlalchemy.orm import Session

        with Session(engine) as s:
            total = s.query(Account).count()
            verified = s.query(Account).filter(Account.email_verified == 1).count()
        ok(f"Accounts stored: {total} total, {verified} verified.")
        if total and verified == total:
            warn(
                "Every account is already verified, so the verify screen will "
                "not appear on login. That is expected for accounts created "
                "before verification was enforced."
            )
    except Exception as exc:
        fail(f"Database error: {exc}", "Delete backend/trialfinder.db and restart to rebuild it.")


# ---------------------------------------------------------------------------
# 3. ClinicalTrials.gov
# ---------------------------------------------------------------------------


def check_ctgov() -> None:
    section("3. ClinicalTrials.gov (trial data, no key needed)")
    try:
        from services import search_service

        text_block = asyncio.run(
            search_service.fetch_ctgov_trials("lung cancer", "New York, NY", max_results=5)
        )
        if not text_block.strip():
            fail(
                "CT.gov returned no trials for a query that should have many.",
                "Check your internet connection or whether the API is reachable.",
            )
            return

        nct_count = text_block.count("NCT ID:")
        ok(f"Returned {nct_count} recruiting trials for a test query.")
        first = [ln for ln in text_block.splitlines() if ln.startswith("Title:")][:2]
        for line in first:
            print(f"        {DIM}{line[:88]}{RESET}")
    except Exception as exc:
        fail(f"CT.gov request failed: {exc}", "Check your network connection.")


# ---------------------------------------------------------------------------
# 4 + 5. LLM provider and web search
# ---------------------------------------------------------------------------


def check_llm() -> None:
    section("4. LLM provider")
    try:
        from services import llm_provider

        provider = llm_provider.active_provider()
        if provider is None:
            fail("No usable provider.", "Add GEMINI_API_KEY or ANTHROPIC_API_KEY to .env")
            return
        ok(f"Active provider resolved to: {provider}")

        print(f"  {DIM}Sending a small test prompt...{RESET}")
        try:
            reply = asyncio.run(
                llm_provider.complete(
                    'Reply with exactly this JSON and nothing else: {"status":"ok"}',
                    # Generous budget: reasoning models spend tokens before
                    # emitting text, and a truncated reply looks like a
                    # failure when the provider is actually fine.
                    max_tokens=2000,
                    json_only=True,
                )
            )
            parsed = llm_provider.parse_json(reply)
            if parsed.get("status") == "ok":
                ok(f"{provider} responded correctly and returned valid JSON.")
            elif reply.strip():
                warn(f"{provider} responded but the JSON was unexpected: {reply[:120]}")
            else:
                fail(f"{provider} returned an empty response.", "Check the key and quota.")
        except Exception as exc:
            msg = str(exc)
            fail(f"{provider} call failed: {msg[:300]}", _llm_fix_hint(provider, msg))
            return

        section("5. Grounded web search")
        result = asyncio.run(llm_provider.search("What is a clinical trial phase II study?"))
        if result.get("answer"):
            ok(f"Search returned {len(result['answer'])} characters.")
            if result.get("sources"):
                ok(f"Search cited {len(result['sources'])} sources.")
            else:
                warn("Search answered but cited no sources. Grounding may be off.")
        else:
            warn(
                "Web search returned nothing. Trial matching still works from "
                "CT.gov data, but drug intel and site reputation will be thin."
            )
    except Exception as exc:
        fail(f"Provider check crashed: {exc}", "Run: pip install -r requirements.txt")


def _llm_fix_hint(provider: str, msg: str) -> str:
    low = msg.lower()
    if provider == "gemini":
        if "api key not valid" in low or "api_key_invalid" in low or "400" in low:
            return (
                "That key is not valid for the Gemini Developer API. Keys from "
                "https://aistudio.google.com/apikey normally start with 'AIza'. "
                "A key starting with 'AQ.' is usually a Google Cloud / Vertex AI "
                "credential, which needs a different setup. Create a Developer "
                "API key at aistudio.google.com/apikey, or switch to Claude by "
                "setting LLM_PROVIDER=claude and adding ANTHROPIC_API_KEY."
            )
        if "quota" in low or "429" in low or "resource_exhausted" in low:
            return "You hit the Gemini rate limit or quota. Wait a minute, or switch LLM_PROVIDER=claude."
        if "permission" in low or "403" in low:
            return "The key lacks permission for the Generative Language API. Enable it in Google Cloud, or make a fresh key at aistudio.google.com/apikey."
    if provider == "claude":
        if "authentication" in low or "401" in low:
            return "ANTHROPIC_API_KEY is invalid. Get one at console.anthropic.com."
        if "credit" in low or "billing" in low:
            return "Your Anthropic account is out of credit. Add credit, or set LLM_PROVIDER=gemini."
    return "Check the key value and that the relevant API is enabled."


# ---------------------------------------------------------------------------
# 6. Email
# ---------------------------------------------------------------------------


def check_email(test_recipient: str | None) -> None:
    section("6. Email delivery")
    from services import email_service

    if not email_service.is_configured():
        warn(
            "No email provider configured. Verification codes will be printed "
            "to this terminal instead of emailed. That is fine for local dev."
        )
        return

    sender = os.getenv("EMAIL_FROM", "")
    # Mirrors the real priority order in email_service._send().
    using_sendgrid = bool(os.getenv("SENDGRID_API_KEY"))
    using_resend = not using_sendgrid and bool(os.getenv("RESEND_API_KEY"))
    using_smtp = not using_sendgrid and not using_resend and bool(os.getenv("SMTP_HOST"))
    provider = "SendGrid" if using_sendgrid else ("Resend" if using_resend else "SMTP")
    ok(f"Provider: {provider}. Sending as: {sender or '(default)'}")

    if using_sendgrid:
        warn(
            "SendGrid requires the EMAIL_FROM address to be a verified Single "
            "Sender (or verified domain) — Settings > Sender Authentication in "
            "the SendGrid dashboard. An unverified sender is rejected with "
            "HTTP 401/403, reported below if you run this with --email."
        )

    if using_resend and "resend.dev" in sender:
        warn(
            "You are using Resend's shared onboarding@resend.dev sender. "
            "A sandboxed Resend account only delivers to the exact address "
            "you signed up with; every other recipient gets HTTP 403. Either "
            "verify a domain at https://resend.com/domains, or switch to SMTP."
        )

    if using_smtp:
        # Catch bad credentials here rather than at signup time.
        import smtplib
        import ssl

        host = os.getenv("SMTP_HOST", "")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER", "")
        password = os.getenv("SMTP_PASSWORD", "")
        try:
            ctx = ssl.create_default_context()
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=20)
            else:
                server = smtplib.SMTP(host, port, timeout=20)
                server.starttls(context=ctx)
            with server:
                server.login(user, password)
            ok(f"SMTP login to {host}:{port} succeeded.")
        except smtplib.SMTPAuthenticationError:
            fail(
                f"SMTP login to {host} was rejected.",
                "For Gmail you need an App Password, not your normal password. "
                "Enable 2-Step Verification, then create one at "
                "https://myaccount.google.com/apppasswords and paste it as "
                "SMTP_PASSWORD (no spaces).",
            )
            return
        except Exception as exc:
            fail(
                f"Could not reach {host}:{port} ({type(exc).__name__}).",
                "Check SMTP_HOST and SMTP_PORT, and that your network allows "
                "outbound SMTP.",
            )
            return

    if not test_recipient:
        print(f"  {DIM}Re-run with --email you@example.com to send a real test.{RESET}")
        return

    print(f"  {DIM}Sending a test code to {test_recipient}...{RESET}")
    sent = email_service.send_verification_code(test_recipient, "123456")
    if sent:
        ok(f"Accepted for delivery to {test_recipient}. Check the inbox and spam folder.")
    elif using_sendgrid:
        fail(
            f"Delivery to {test_recipient} was rejected. The reason is logged above.",
            "If it mentions a Sender Identity, verify EMAIL_FROM's address "
            "under SendGrid > Settings > Sender Authentication.",
        )
    else:
        fail(
            f"Delivery to {test_recipient} was rejected. The reason is logged above.",
            "If it mentions 'testing emails', use the address you registered "
            "with Resend, or verify a domain at https://resend.com/domains "
            "and set EMAIL_FROM to an address on it.",
        )


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose TrialFinder setup")
    parser.add_argument("--email", help="Send a real test email to this address")
    args = parser.parse_args()

    print(f"\n{BOLD}TrialFinder diagnostics{RESET}")
    print("=" * 60)

    check_env()
    check_database()
    check_ctgov()
    check_llm()
    check_email(args.email)

    print("\n" + "=" * 60)
    if _failures:
        print(f"{RED}{BOLD}{len(_failures)} problem(s) found:{RESET}")
        for f in _failures:
            print(f"  - {f}")
        print("\nFix the items above, then run this again.")
        return 1

    print(f"{GREEN}{BOLD}Everything checks out.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
