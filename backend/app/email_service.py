from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

import resend

from app.config import get_settings
from app.fetchers.deeplinks import build_deep_link, is_generic_link

FROM_ADDRESS = "PrintTender India <alerts@printtender.in>"
SAFFRON = "#f97316"
BG = "#111827"
PANEL = "#1f2937"
TEXT = "#f8fafc"
MUTED = "#94a3b8"


def send_confirmation_email(to_email: str, keyword: str, confirm_url: str) -> bool:
    html = _shell(
        title="Confirm your tender alert",
        body=f"""
        <p style="margin:0 0 18px;color:{MUTED};font-size:15px;line-height:1.6">
          Confirm your PrintTender India alert for
          <strong style="color:{TEXT}">{escape(keyword)}</strong>.
        </p>
        {_button("Confirm Alert", confirm_url)}
        <p style="margin:22px 0 0;color:{MUTED};font-size:12px;line-height:1.5">
          If you did not request this alert, you can ignore this email.
        </p>
        """,
    )
    return _send(
        to_email,
        "Confirm your PrintTender India alert",
        html,
        f"Confirm your alert for {keyword}: {confirm_url}",
    )


def send_tender_alert_email(
    to_email: str,
    keyword: str,
    tenders: list[Any],
    *,
    unsubscribe_url: str | None = None,
) -> bool:
    visible = tenders[:10]
    extra_count = max(0, len(tenders) - len(visible))
    cards = "".join(_tender_card(tender) for tender in visible)
    dashboard_url = get_settings().FRONTEND_URL
    extra = (
        f"""
        <p style="margin:18px 0 0;color:{MUTED};font-size:14px">
          {extra_count} more matching tenders are available on the dashboard.
        </p>
        {_button("Open Dashboard", dashboard_url)}
        """
        if extra_count
        else ""
    )
    unsub = (
        f'<p style="margin:20px 0 0;color:{MUTED};font-size:12px">'
        f'<a href="{escape(unsubscribe_url)}" style="color:{MUTED}">Unsubscribe</a></p>'
        if unsubscribe_url
        else ""
    )
    html = _shell(
        title=f"New tenders for {escape(keyword)}",
        body=f"""
        <p style="margin:0 0 18px;color:{MUTED};font-size:15px;line-height:1.6">
          We found {len(tenders)} tender{"" if len(tenders) == 1 else "s"} matching
          <strong style="color:{TEXT}">{escape(keyword)}</strong>.
        </p>
        {cards}
        {extra}
        {unsub}
        """,
    )
    return _send(
        to_email,
        f"PrintTender India: {len(tenders)} new tender matches",
        html,
        f"{len(tenders)} tenders matched {keyword}. Open {dashboard_url}",
    )


def send_unsubscribe_confirmation_email(
    to_email: str, keyword: str | None = None
) -> bool:
    label = f" for {keyword}" if keyword else ""
    html = _shell(
        title="Alert unsubscribed",
        body=f"""
        <p style="margin:0;color:{MUTED};font-size:15px;line-height:1.6">
          Your PrintTender India alert{escape(label)} has been unsubscribed.
        </p>
        """,
    )
    return _send(
        to_email,
        "PrintTender India alert unsubscribed",
        html,
        f"Your PrintTender India alert{label} has been unsubscribed.",
    )


def _send(to_email: str, subject: str, html: str, text: str) -> bool:
    settings = get_settings()
    if not settings.RESEND_API_KEY:
        print(f"[email dry-run] to={to_email} subject={subject}\n{text}")
        return True
    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": FROM_ADDRESS,
                "to": [to_email],
                "subject": subject,
                "html": html,
                "text": text,
            }
        )
        return True
    except Exception as exc:
        print(f"[email skipped] to={to_email} subject={subject} error={exc}")
        return False


def _shell(title: str, body: str) -> str:
    return f"""
    <div style="margin:0;padding:0;background:{BG};font-family:Inter,Arial,sans-serif;color:{TEXT}">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{BG};padding:24px 12px">
        <tr>
          <td align="center">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:{PANEL};border:1px solid rgba(255,255,255,.08);border-radius:14px;overflow:hidden">
              <tr>
                <td style="padding:22px 24px;border-bottom:3px solid {SAFFRON}">
                  <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:{SAFFRON};font-weight:700">PrintTender India</div>
                  <h1 style="margin:8px 0 0;font-size:24px;line-height:1.25;color:{TEXT}">{escape(title)}</h1>
                </td>
              </tr>
              <tr>
                <td style="padding:24px">{body}</td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </div>
    """


def _button(label: str, url: str) -> str:
    return f"""
    <p style="margin:22px 0 0">
      <a href="{escape(url)}" style="display:inline-block;background:{SAFFRON};color:#111827;text-decoration:none;font-weight:800;border-radius:8px;padding:12px 18px">
        {escape(label)}
      </a>
    </p>
    """


def _tender_card(tender: Any) -> str:
    title = _get(tender, "title") or "Tender notice"
    organisation = _get(tender, "organisation") or "Not specified"
    state = _get(tender, "state") or "India"
    deadline = _get(tender, "bid_end_date")
    url = _deep_link_for(tender)
    deadline_label, deadline_color = _deadline_display(deadline)
    return f"""
    <div style="border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:16px;margin:0 0 12px;background:#172033">
      <h2 style="margin:0 0 8px;font-size:16px;line-height:1.35;color:{TEXT}">{escape(str(title))}</h2>
      <p style="margin:0 0 6px;color:{MUTED};font-size:13px;line-height:1.5">{escape(str(organisation))}</p>
      <p style="margin:0 0 10px;color:{MUTED};font-size:13px">
        {escape(str(state))}
      </p>
      <p style="margin:0 0 14px;color:{deadline_color};font-size:13px;font-weight:700">{escape(deadline_label)}</p>
      <a href="{escape(url)}" style="display:inline-block;color:{SAFFRON};font-weight:800;text-decoration:none">View and Apply</a>
    </div>
    """


def _deep_link_for(tender: Any) -> str:
    url = _get(tender, "portal_url") or ""
    if url and not is_generic_link(url):
        return str(url)
    return build_deep_link(
        str(_get(tender, "portal_source") or ""),
        str(_get(tender, "ref_number") or ""),
        _get(tender, "tender_id"),
    )


def _deadline_display(value: Any) -> tuple[str, str]:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value, MUTED
    if not isinstance(value, datetime):
        return "Deadline not specified", MUTED
    deadline = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    days = (deadline.astimezone(timezone.utc) - datetime.now(timezone.utc)).days
    label = deadline.strftime("%d %b %Y")
    if days <= 3:
        return f"Urgent: closes {label}", "#f87171"
    if days <= 7:
        return f"Closes {label}", "#fbbf24"
    return f"Closes {label}", "#34d399"


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
