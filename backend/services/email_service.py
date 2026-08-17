"""
Email delivery for verification codes, password resets, and watchlist alerts.

Four delivery paths, tried in order:

1. SendGrid HTTP API — set SENDGRID_API_KEY. Needs only a verified Single
                       Sender (click a confirmation link — no domain or DNS
                       required), so it works even where outbound SMTP is
                       blocked. Railway's network blocks raw SMTP traffic
                       (confirmed: SMTP send fails there with
                       "[Errno 101] Network is unreachable"), so this is the
                       path that actually works when deployed there.
2. Resend HTTP API   — set RESEND_API_KEY. Also HTTPS-based, but its shared
                       sandbox sender can only deliver to the email address
                       the Resend account itself was signed up with, unless
                       you verify a full domain.
3. SMTP              — set SMTP_HOST, SMTP_USER, SMTP_PASSWORD. Works with a
                       free Gmail account using an App Password. Fine for
                       local dev; blocked on platforms like Railway that
                       filter outbound SMTP to prevent abuse.
4. Log only          — none configured. The email body is written to the
                       server log so local dev still works.

Provider is chosen automatically; you only need to configure one.
"""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

import httpx

logger = logging.getLogger(__name__)

_RESEND_API = "https://api.resend.com/emails"
_SENDGRID_API = "https://api.sendgrid.com/v3/mail/send"


def _api_key() -> str:
    return os.getenv("RESEND_API_KEY", "")


def _sendgrid_key() -> str:
    return os.getenv("SENDGRID_API_KEY", "")


def _smtp_configured() -> bool:
    return bool(
        os.getenv("SMTP_HOST")
        and os.getenv("SMTP_USER")
        and os.getenv("SMTP_PASSWORD")
    )


def is_configured() -> bool:
    """True when any real delivery path is available."""
    return bool(_sendgrid_key()) or bool(_api_key()) or _smtp_configured()


def _from_address() -> str:
    """
    The From header.

    Note on Gmail SMTP: Gmail rewrites this to the authenticated account
    unless the address is a verified alias on that account, so setting
    EMAIL_FROM to an arbitrary address will NOT hide the sending mailbox.
    To keep a personal address off outgoing mail, authenticate as a dedicated
    account (e.g. a project-specific Gmail), or use a provider with a
    verified domain.
    """
    explicit = os.getenv("EMAIL_FROM")
    if explicit:
        return explicit
    if _smtp_configured():
        return os.getenv("SMTP_USER", "")
    return "TrialFinder <onboarding@resend.dev>"


def _reply_to() -> str | None:
    """
    Optional Reply-To. Unlike From, this is not rewritten, so it is the one
    reliable way to route replies somewhere other than the sending mailbox.
    """
    return os.getenv("EMAIL_REPLY_TO") or None


def _parse_from(addr: str) -> tuple[str, str]:
    """
    Split "Name <email@x.com>" into (name, email).

    SendGrid's API wants the display name and address as separate JSON
    fields, unlike the single header string SMTP/Resend accept.
    """
    name, email_addr = parseaddr(addr)
    return name, email_addr or addr


def _send_via_sendgrid(to_email: str, subject: str, text: str, html: str) -> bool:
    """
    Send through SendGrid's HTTPS API.

    Only needs a verified Single Sender (SendGrid > Settings > Sender
    Authentication > click a confirmation link) — no domain or DNS records
    required, unlike Resend without a verified domain. Because this is a
    plain HTTPS POST, it also works on platforms that block outbound SMTP.
    """
    key = _sendgrid_key()
    name, sender_email = _parse_from(_from_address())
    from_field = {"email": sender_email}
    if name:
        from_field["name"] = name

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": from_field,
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text},
            {"type": "text/html", "value": html},
        ],
    }
    reply_to = _reply_to()
    if reply_to:
        payload["reply_to"] = {"email": reply_to}

    try:
        resp = httpx.post(
            _SENDGRID_API,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )
    except Exception as exc:
        logger.error("Could not reach SendGrid to email %s: %s", to_email, exc)
        return False

    if resp.status_code >= 400:
        # SendGrid puts the real reason in the response body. Without this
        # the failure is invisible and looks like "the email just never
        # arrived".
        body = (resp.text or "")[:500]
        logger.error(
            "SendGrid rejected the email to %s (HTTP %s). from=%r response=%s",
            to_email,
            resp.status_code,
            sender_email,
            body,
        )
        if resp.status_code in (401, 403):
            logger.error(
                "HINT: SendGrid requires the 'from' address to be a verified "
                "Single Sender (or a verified domain). Verify %r under "
                "SendGrid > Settings > Sender Authentication.",
                sender_email,
            )
        return False

    logger.info("Sent email to %s via SendGrid", to_email)
    return True


def _send_via_smtp(to_email: str, subject: str, text: str, html: str) -> bool:
    """Send through a standard SMTP server (Gmail, Fastmail, SES, etc.)."""
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _from_address()
    msg["To"] = to_email
    reply_to = _reply_to()
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    try:
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.send_message(msg)
    except Exception as exc:
        logger.error("SMTP send to %s failed: %s", to_email, exc)
        return False

    logger.info("Sent email to %s via SMTP", to_email)
    return True


def send_verification_code(to_email: str, code: str) -> bool:
    """Send the 6-digit verification code. Falls back to logging when no key."""
    subject = "Your TrialFinder verification code"
    text = (
        f"Welcome to TrialFinder.\n\n"
        f"Your verification code is: {code}\n\n"
        f"Enter it on the verification screen to activate your account. "
        f"If you did not sign up, you can ignore this email."
    )
    html = f"""
    <div style="font-family:system-ui,Arial,sans-serif;max-width:480px;margin:0 auto;color:#14202e;">
      <h2 style="font-size:20px;">Welcome to TrialFinder</h2>
      <p>Your verification code is:</p>
      <p style="font-size:28px;font-weight:800;letter-spacing:0.2em;color:#1f6feb;background:#eaf1fe;padding:14px 18px;border-radius:10px;text-align:center;">{_esc(code)}</p>
      <p style="color:#4a5a6a;">Enter it on the verification screen to activate your account.
      If you did not sign up, you can safely ignore this email.</p>
    </div>
    """
    return _send(to_email, subject, text, html)


def send_password_reset(to_email: str, code: str) -> bool:
    """Send a password reset code."""
    subject = "Reset your TrialFinder password"
    text = (
        f"We received a request to reset your TrialFinder password.\n\n"
        f"Your reset code is: {code}\n\n"
        f"This code expires in 30 minutes. If you did not request a reset, "
        f"you can ignore this email and your password will stay the same."
    )
    html = f"""
    <div style="font-family:system-ui,Arial,sans-serif;max-width:480px;margin:0 auto;color:#14202e;">
      <h2 style="font-size:20px;">Reset your password</h2>
      <p>We received a request to reset your TrialFinder password. Your code is:</p>
      <p style="font-size:28px;font-weight:800;letter-spacing:0.2em;color:#1f6feb;background:#eaf1fe;padding:14px 18px;border-radius:10px;text-align:center;">{_esc(code)}</p>
      <p style="color:#4a5a6a;">This code expires in 30 minutes. If you did not
      request a reset, you can ignore this email and your password will stay the same.</p>
    </div>
    """
    return _send(to_email, subject, text, html)


def _send(to_email: str, subject: str, text: str, html: str) -> bool:
    # Path 1: SendGrid. Checked first — it's the one path that works
    # regardless of whether the host blocks outbound SMTP, and needs only a
    # verified single sender rather than a verified domain.
    if _sendgrid_key():
        return _send_via_sendgrid(to_email, subject, text, html)

    key = _api_key()

    # Path 3: SMTP, when no Resend key but SMTP is configured.
    if not key and _smtp_configured():
        return _send_via_smtp(to_email, subject, text, html)

    # Path 4: log only.
    if not key:
        logger.warning(
            "No email provider configured (set SENDGRID_API_KEY, "
            "RESEND_API_KEY, or SMTP_*). Would have emailed %s:\nSubject: %s\n%s",
            to_email, subject, text,
        )
        # Return False, not True. Nothing was actually delivered, and callers
        # rely on this to decide whether to surface the one-time code in the
        # response. Claiming success here strands the user on the verify
        # screen waiting for an email that will never arrive.
        return False

    # Path 2: Resend.
    sender = _from_address()
    payload = {
        "from": sender,
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text,
    }
    reply_to = _reply_to()
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        resp = httpx.post(
            _RESEND_API,
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=15.0,
        )
    except Exception as exc:
        logger.error("Could not reach Resend to email %s: %s", to_email, exc)
        return False

    if resp.status_code >= 400:
        # Resend puts the real reason in the response body. Without this the
        # failure is invisible and looks like "the email just never arrived".
        body = (resp.text or "")[:500]
        logger.error(
            "Resend rejected the email to %s (HTTP %s). from=%r response=%s",
            to_email,
            resp.status_code,
            sender,
            body,
        )
        if resp.status_code == 403 and "testing emails" in body.lower():
            logger.error(
                "HINT: Resend's shared onboarding@resend.dev sender can only "
                "deliver to the email address you signed up to Resend with. "
                "Either register using that same address, or verify your own "
                "domain at https://resend.com/domains and set EMAIL_FROM to it."
            )
        return False

    logger.info("Sent email to %s via Resend", to_email)
    return True


def send_watchlist_digest(
    to_email: str,
    changes: list[dict],
    *,
    unsubscribe_token: str | None = None,
) -> bool:
    """
    Send one digest covering every changed trial for a user.

    `changes` is a list of dicts:
        {nct_id, title, source_url, profile_label, severity, changes: [str]}

    Routed through the shared _send(), so it works with Resend, SMTP, or the
    log-only fallback. Returns False only on a hard delivery failure.
    """
    if not changes:
        return True

    subject = _subject(changes)
    html = _render_html(changes, unsubscribe_token)
    text = _render_text(changes, unsubscribe_token)

    sent = _send(to_email, subject, text, html)
    if sent:
        logger.info(
            "email.digest_sent to=%s trials=%d high_priority=%d",
            to_email,
            len(changes),
            sum(1 for c in changes if c.get("severity") == "high"),
        )
    return sent


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _app_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")[0].strip().rstrip("/")


def _api_url() -> str:
    return os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")


def _unsubscribe_link(token: str | None) -> str | None:
    if not token:
        return None
    return f"{_api_url()}/api/alerts/unsubscribe?token={token}"


def _subject(changes: list[dict]) -> str:
    urgent = [c for c in changes if c.get("severity") == "high"]
    n = len(changes)

    if urgent:
        first = urgent[0]["title"][:50]
        if len(urgent) == 1 and n == 1:
            return f"Important update: {first}"
        return f"Important update on {len(urgent)} of your saved trials"

    if n == 1:
        return f"Update on a trial you're watching: {changes[0]['title'][:55]}"
    return f"{n} of your saved clinical trials have updates"


def _render_text(changes: list[dict], token: str | None = None) -> str:
    lines = ["Here is what changed in the trials you are following.\n"]

    for c in changes:
        flag = "[IMPORTANT] " if c.get("severity") == "high" else ""
        who = f"[{c['profile_label']}] " if c.get("profile_label") else ""
        lines.append(f"{flag}{who}{c['title']} ({c['nct_id']})")
        for ch in c["changes"]:
            lines.append(f"    - {ch}")
        if c.get("source_url"):
            lines.append(f"    View: {c['source_url']}")
        lines.append("")

    lines.append(f"See all your saved trials: {_app_url()}/watchlist")
    lines.append("")
    lines.append(
        "This is informational only and is not medical advice. Confirm any "
        "trial's status with its study team and discuss decisions with your "
        "healthcare provider."
    )
    link = _unsubscribe_link(token)
    if link:
        lines.append("")
        lines.append(f"To stop these emails: {link}")
    return "\n".join(lines)


def _render_html(changes: list[dict], token: str | None = None) -> str:
    items = []
    for c in changes:
        high = c.get("severity") == "high"
        change_items = "".join(f"<li>{_esc(ch)}</li>" for ch in c["changes"])

        badge = (
            '<span style="display:inline-block;background:#fdecec;color:#88231d;'
            'font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;'
            'margin-bottom:6px;">IMPORTANT</span><br>'
            if high
            else ""
        )
        who = (
            f'<p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#1f6feb;">'
            f"For {_esc(c['profile_label'])}</p>"
            if c.get("profile_label")
            else ""
        )
        link = (
            f'<p style="margin:10px 0 0;"><a href="{_esc(c["source_url"])}" '
            f'style="color:#1f6feb;">View on ClinicalTrials.gov</a></p>'
            if c.get("source_url")
            else ""
        )
        border = "#d05249" if high else "#e3e9f0"

        items.append(
            f"""
            <div style="margin:0 0 16px;padding:16px;border:1px solid {border};border-radius:10px;">
              {badge}{who}
              <h3 style="margin:0 0 4px;font-size:16px;color:#14202e;">{_esc(c['title'])}</h3>
              <p style="margin:0 0 10px;color:#7d8b99;font-size:13px;">{_esc(c['nct_id'])}</p>
              <ul style="margin:0;padding-left:18px;color:#14202e;font-weight:600;line-height:1.6;">{change_items}</ul>
              {link}
            </div>
            """
        )

    unsub = _unsubscribe_link(token)
    unsub_html = (
        f'<p style="font-size:12px;color:#7d8b99;margin-top:10px;">'
        f'You are receiving this because you saved these trials on TrialFinder. '
        f'<a href="{_esc(unsub)}" style="color:#7d8b99;">Unsubscribe from trial alerts</a>.'
        f"</p>"
        if unsub
        else ""
    )

    return f"""
    <div style="font-family:system-ui,-apple-system,Arial,sans-serif;max-width:580px;margin:0 auto;color:#14202e;padding:8px;">
      <h2 style="font-size:20px;margin:0 0 4px;">Updates to your saved trials</h2>
      <p style="color:#4a5a6a;font-size:14px;margin:0 0 18px;">
        Here is what changed since we last checked.
      </p>
      {''.join(items)}
      <p style="margin:18px 0;">
        <a href="{_esc(_app_url())}/watchlist"
           style="display:inline-block;background:#1f6feb;color:#ffffff;text-decoration:none;
                  padding:10px 18px;border-radius:999px;font-weight:600;font-size:14px;">
          View all saved trials
        </a>
      </p>
      <p style="font-size:12px;color:#7d8b99;border-top:1px solid #e3e9f0;padding-top:12px;line-height:1.5;">
        This is informational only and is not medical advice. Trial information
        comes from ClinicalTrials.gov and may change. Confirm any trial's status
        with its study team, and discuss decisions with a qualified healthcare
        provider.
      </p>
      {unsub_html}
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
