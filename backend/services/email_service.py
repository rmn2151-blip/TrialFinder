"""
Email delivery for watchlist alerts.

Uses Resend's HTTP API (https://resend.com) via httpx — no extra SDK needed.
If RESEND_API_KEY is not set, the service degrades gracefully: it logs the
email it *would* have sent and returns True, so the rest of the flow (and the
demo) works without any email provider configured.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_RESEND_API = "https://api.resend.com/emails"


def _api_key() -> str:
    return os.getenv("RESEND_API_KEY", "")


def _from_address() -> str:
    # Resend allows onboarding@resend.dev for testing without domain setup.
    return os.getenv("EMAIL_FROM", "TrialFinder <onboarding@resend.dev>")


def send_watchlist_digest(to_email: str, changes: list[dict]) -> bool:
    """
    Send a digest of changed trials to one user.

    `changes` is a list of dicts: {nct_id, title, source_url, changes: [str]}.
    Returns True if sent (or logged in fallback mode), False on hard failure.
    """
    subject = _subject(changes)
    html = _render_html(changes)
    text = _render_text(changes)

    key = _api_key()
    if not key:
        logger.warning(
            "RESEND_API_KEY not set — would email %s:\nSubject: %s\n%s",
            to_email,
            subject,
            text,
        )
        return True  # treat as success so the sweep reports accurately in dev

    try:
        resp = httpx.post(
            _RESEND_API,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "from": _from_address(),
                "to": [to_email],
                "subject": subject,
                "html": html,
                "text": text,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to send watchlist email to %s: %s", to_email, exc)
        return False

    logger.info("Sent watchlist digest to %s (%d trials)", to_email, len(changes))
    return True


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _subject(changes: list[dict]) -> str:
    n = len(changes)
    if n == 1:
        return f"Update on a clinical trial you're watching: {changes[0]['title'][:60]}"
    return f"{n} of your watched clinical trials have updates"


def _render_text(changes: list[dict]) -> str:
    lines = ["Here's what changed in the trials you're watching:\n"]
    for c in changes:
        who = f"[{c['profile_label']}] " if c.get("profile_label") else ""
        lines.append(f"• {who}{c['title']} ({c['nct_id']})")
        for ch in c["changes"]:
            lines.append(f"    - {ch}")
        if c.get("source_url"):
            lines.append(f"    View: {c['source_url']}")
        lines.append("")
    lines.append(
        "This is informational only and not medical advice. "
        "Discuss any trial with your healthcare provider."
    )
    return "\n".join(lines)


def _render_html(changes: list[dict]) -> str:
    items = []
    for c in changes:
        change_items = "".join(f"<li>{_esc(ch)}</li>" for ch in c["changes"])
        link = (
            f'<p><a href="{_esc(c["source_url"])}">View on ClinicalTrials.gov →</a></p>'
            if c.get("source_url")
            else ""
        )
        who = (
            f'<p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#1f6feb;">For {_esc(c["profile_label"])}</p>'
            if c.get("profile_label")
            else ""
        )
        items.append(
            f"""
            <div style="margin:0 0 20px;padding:16px;border:1px solid #e3e9f0;border-radius:10px;">
              {who}
              <h3 style="margin:0 0 4px;font-size:16px;color:#14202e;">{_esc(c['title'])}</h3>
              <p style="margin:0 0 8px;color:#7d8b99;font-size:13px;">{_esc(c['nct_id'])}</p>
              <ul style="margin:0;padding-left:18px;color:#1f6feb;font-weight:600;">{change_items}</ul>
              {link}
            </div>
            """
        )
    return f"""
    <div style="font-family:system-ui,Arial,sans-serif;max-width:560px;margin:0 auto;color:#14202e;">
      <h2 style="font-size:20px;">Updates to trials you're watching</h2>
      {''.join(items)}
      <p style="font-size:12px;color:#7d8b99;border-top:1px solid #e3e9f0;padding-top:12px;">
        This is informational only and not medical advice. Always discuss clinical
        trials with a qualified healthcare provider.
      </p>
    </div>
    """


def _esc(s) -> str:
    s = "" if s is None else str(s)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
