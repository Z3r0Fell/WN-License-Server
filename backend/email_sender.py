"""Email delivery: SendGrid HTTP API (preferred) -> SMTP fallback -> log-only."""
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Optional

logger = logging.getLogger("watchnexus.email")


def _provider() -> str:
    if os.environ.get("SENDGRID_API_KEY"):
        return "sendgrid"
    if os.environ.get("SMTP_HOST"):
        return "smtp"
    return "log"


def _from_addr() -> tuple[str, str]:
    addr = os.environ.get("EMAIL_FROM", "licenses@watchnexus.app")
    name = os.environ.get("EMAIL_FROM_NAME", "WatchNexus")
    return name, addr


def send_email(to: str, subject: str, html: str, text: Optional[str] = None) -> dict:
    """Best-effort send. Never raises - returns dict with status & provider."""
    if not to:
        return {"sent": False, "provider": "none", "reason": "missing recipient"}
    provider = _provider()
    name, addr = _from_addr()
    text = text or _html_to_text(html)
    try:
        if provider == "sendgrid":
            return _send_sendgrid(addr, name, to, subject, html, text)
        if provider == "smtp":
            return _send_smtp(addr, name, to, subject, html, text)
        # Log-only fallback
        logger.info(f"[email:log-only] to={to} subject={subject!r}")
        return {"sent": False, "provider": "log", "reason": "no email provider configured"}
    except Exception as e:
        logger.exception("send_email failed")
        return {"sent": False, "provider": provider, "error": str(e)}


def _send_sendgrid(from_addr: str, from_name: str, to: str, subject: str, html: str, text: str) -> dict:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    msg = Mail(
        from_email=Email(from_addr, from_name),
        to_emails=To(to),
        subject=subject,
        plain_text_content=Content("text/plain", text),
        html_content=Content("text/html", html),
    )
    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    res = sg.send(msg)
    return {"sent": 200 <= res.status_code < 300, "provider": "sendgrid", "status": res.status_code}


def _send_smtp(from_addr: str, from_name: str, to: str, subject: str, html: str, text: str) -> dict:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USERNAME")
    pw = os.environ.get("SMTP_PASSWORD")
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    msg = EmailMessage()
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        s = smtplib.SMTP(host, port, timeout=15)
        if use_tls:
            s.starttls()
    try:
        if user and pw:
            s.login(user, pw)
        s.send_message(msg)
    finally:
        s.quit()
    return {"sent": True, "provider": "smtp"}


def _html_to_text(html: str) -> str:
    import re
    txt = re.sub(r"<br ?/?>", "\n", html, flags=re.I)
    txt = re.sub(r"</p>", "\n\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    return txt.strip()


def render_purchase_email(*, customer_email: str, license_key: str, product_name: str,
                          plan: str, seats: int, source: str, portal_url: str) -> tuple[str, str]:
    subject = f"Your {product_name} license"
    html = f"""
<!doctype html>
<html><body style="font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0B1220;color:#E2E8F0;margin:0;padding:0;">
  <div style="max-width:560px;margin:0 auto;padding:32px 24px;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:24px;">
      <div style="width:28px;height:28px;border-radius:8px;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.3);display:inline-block;"></div>
      <div style="font-weight:600;letter-spacing:.02em;">WatchNexus</div>
    </div>
    <h1 style="font-size:22px;margin:0 0 8px 0;letter-spacing:-.01em;">Your license is ready</h1>
    <p style="color:#94A3B8;margin:0 0 24px 0;">Thanks for purchasing <b>{product_name}</b> ({plan} · {seats} seat{'s' if seats != 1 else ''}). Here is your license key.</p>
    <div style="font-family:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;font-size:13px;letter-spacing:.06em;background:#0F172A;border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:16px;word-break:break-all;color:#A7F3D0;">{license_key}</div>
    <p style="color:#94A3B8;margin:24px 0 8px 0;font-size:14px;">Activate your install with this key. Manage your devices, download builds, and view future invoices in your portal:</p>
    <p><a href="{portal_url}" style="display:inline-block;background:#10B981;color:#022c22;text-decoration:none;font-weight:600;padding:10px 16px;border-radius:10px;">Open customer portal</a></p>
    <hr style="border:0;border-top:1px solid rgba(255,255,255,.08);margin:32px 0;"/>
    <p style="color:#64748B;font-size:12px;">Provisioned via {source}. Keep this email; the key won’t be shown in plaintext after first display in the portal.</p>
  </div>
</body></html>"""
    return subject, html
