from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape
import smtplib
from typing import Any

import resend

from app.config import get_settings
from app.fetchers.deeplinks import build_deep_link, is_generic_link

DEFAULT_FROM_ADDRESS = "PrintTender India <alerts@printtender.in>"
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
    visible = tenders[:15]
    table_html = _tenders_table(visible)
    dashboard_url = get_settings().FRONTEND_URL
    unsub = (
        f'<p style="margin:20px 0 0;text-align:center;color:{MUTED};font-size:12px">'
        f'<a href="{escape(unsubscribe_url)}" style="color:{MUTED}">Unsubscribe</a></p>'
        if unsubscribe_url
        else ""
    )
    html = _shell(
        title="Daily PrintTender India Alert",
        body=f"""
        <p style="margin:0 0 16px;color:{MUTED};font-size:15px;line-height:1.6">
          Here is your daily tender update matching
          <strong style="color:{TEXT}">{escape(keyword)}</strong> ({len(tenders)} active tender{"" if len(tenders) == 1 else "s"}).
        </p>
        {table_html}
        {_open_site_button(dashboard_url)}
        {unsub}
        """,
    )
    return _send(
        to_email,
        f"PrintTender India: Daily {escape(keyword)} Tenders ({len(tenders)})",
        html,
        f"{len(tenders)} active tenders for {keyword}. Open {dashboard_url}",
    )


def send_test_tender_email(to_email: str, keywords: list[str]) -> bool:
    keyword_label = ", ".join(keywords) if keywords else "printing"
    sample_tender = {
        "title": "Sample Tender - Printing & Stationery Supply",
        "organisation": "PrintTender India",
        "state": "India",
        "bid_end_date": datetime.now(timezone.utc),
        "portal_url": get_settings().FRONTEND_URL,
        "portal_source": "PrintTender",
        "ref_number": "TEST-MAIL",
        "tender_id": None,
        "value_inr": 250000.0,
    }
    dashboard_url = get_settings().FRONTEND_URL
    html = _shell(
        title="PrintTender India Test Mail",
        body=f"""
        <p style="margin:0 0 16px;color:{MUTED};font-size:15px;line-height:1.6">
          This is a sample of your daily tender digest email for
          <strong style="color:{TEXT}">{escape(keyword_label)}</strong>.
        </p>
        {_tenders_table([sample_tender])}
        {_open_site_button(dashboard_url)}
        """,
    )
    return _send(
        to_email,
        "PrintTender India Test Mail",
        html,
        f"Test tender mail for {keyword_label}. Open {dashboard_url}",
    )


def send_all_categories_email(to_email: str, tenders: list[Any] | None = None) -> bool:
    dashboard_url = get_settings().FRONTEND_URL
    table_html = _tenders_table((tenders or [])[:15])
    html = _shell(
        title="Daily Printing Tenders Digest",
        body=f"""
        <p style="margin:0 0 16px;color:{MUTED};font-size:15px;line-height:1.6">
          Here is your daily overview of active government printing press tenders from across India.
        </p>
        {table_html}
        {_open_site_button(dashboard_url)}
        """,
    )
    return _send(
        to_email,
        "PrintTender India: Daily Tenders Update",
        html,
        f"PrintTender India daily printing tender digest. Visit {dashboard_url} to view all tenders.",
    )


def _open_site_button(url: str) -> str:
    return f"""
    <div style="text-align:center;margin:28px 0 12px">
      <a href="{escape(url)}" style="display:inline-block;background:{SAFFRON};color:#111827;text-decoration:none;font-weight:800;font-size:15px;border-radius:8px;padding:14px 28px;box-shadow:0 4px 12px rgba(249,115,22,0.3)">
        Open Site to View All Tenders
      </a>
    </div>
    """


def _tenders_table(tenders: list[Any]) -> str:
    if not tenders:
        return f'<p style="margin:16px 0;color:{MUTED};font-size:14px">No active tenders available today.</p>'

    rows = []
    for idx, t in enumerate(tenders, 1):
        title = _get(t, "title") or "Tender notice"
        organisation = _get(t, "organisation") or "Not specified"
        state = _get(t, "state") or "India"
        portal_source = _get(t, "portal_source") or "Portal"
        ref_number = _get(t, "ref_number") or ""
        deadline = _get(t, "bid_end_date")
        value = _get(t, "value_inr")
        url = _deep_link_for(t)

        deadline_label, deadline_color = _deadline_display(deadline)
        value_label = _value_display(value) or "-"
        ref_display = ref_number[:18] + ("..." if len(ref_number) > 18 else "")

        bg_color = "#172033" if idx % 2 == 1 else "#1f2937"
        rows.append(f"""
        <tr style="background:{bg_color};border-bottom:1px solid rgba(255,255,255,0.06)">
          <td style="padding:10px 8px;vertical-align:top;color:{MUTED};font-size:12px;font-weight:700">{idx}</td>
          <td style="padding:10px 8px;vertical-align:top">
            <div style="font-weight:700;color:{TEXT};font-size:13px;line-height:1.35;margin-bottom:3px">{escape(str(title))}</div>
            <div style="color:{MUTED};font-size:11px">{escape(str(organisation))} &bull; <span style="color:#cbd5e1">{escape(str(state))}</span></div>
          </td>
          <td style="padding:10px 8px;vertical-align:top;font-size:11px;color:{MUTED}">
            <strong style="color:{TEXT}">{escape(str(portal_source))}</strong><br>
            <span style="font-family:monospace;font-size:10px">{escape(str(ref_display))}</span>
          </td>
          <td style="padding:10px 8px;vertical-align:top;font-size:11px;color:{deadline_color};font-weight:700">{escape(deadline_label)}</td>
          <td style="padding:10px 8px;vertical-align:top;text-align:right;font-size:11px;font-family:monospace;color:{TEXT};font-weight:700">{escape(value_label)}</td>
          <td style="padding:10px 8px;vertical-align:top;text-align:center">
            <a href="{escape(url)}" style="display:inline-block;background:{SAFFRON};color:#111827;text-decoration:none;font-weight:800;font-size:11px;border-radius:4px;padding:5px 9px;white-space:nowrap">View</a>
          </td>
        </tr>
        """)

    return f"""
    <div style="overflow-x:auto;margin:16px 0;border:1px solid rgba(255,255,255,0.08);border-radius:8px">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;font-size:13px">
        <thead>
          <tr style="background:#0f172a;border-bottom:2px solid {SAFFRON}">
            <th style="padding:10px 8px;text-align:left;color:{MUTED};font-size:11px;text-transform:uppercase">#</th>
            <th style="padding:10px 8px;text-align:left;color:{MUTED};font-size:11px;text-transform:uppercase">Tender Title & Organisation</th>
            <th style="padding:10px 8px;text-align:left;color:{MUTED};font-size:11px;text-transform:uppercase">Portal / Ref</th>
            <th style="padding:10px 8px;text-align:left;color:{MUTED};font-size:11px;text-transform:uppercase">Deadline</th>
            <th style="padding:10px 8px;text-align:right;color:{MUTED};font-size:11px;text-transform:uppercase">Value</th>
            <th style="padding:10px 8px;text-align:center;color:{MUTED};font-size:11px;text-transform:uppercase">Action</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


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
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
        return _send_smtp(to_email, subject, html, text)

    if not settings.RESEND_API_KEY:
        print(f"[email dry-run] to={to_email} subject={subject}\n{text}")
        return settings.APP_ENV != "production"
    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM or DEFAULT_FROM_ADDRESS,
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


def _send_smtp(to_email: str, subject: str, html: str, text: str) -> bool:
    settings = get_settings()
    host = settings.SMTP_HOST or "smtp.gmail.com"
    from_address = settings.EMAIL_FROM or settings.SMTP_USERNAME

    message = EmailMessage()
    message["From"] = from_address
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(host, settings.SMTP_PORT, timeout=20) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception as exc:
        print(f"[smtp email skipped] to={to_email} subject={subject} error={exc}")
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


def _compact_tender_row(tender: Any) -> str:
    title = _get(tender, "title") or "Tender notice"
    organisation = _get(tender, "organisation") or "Not specified"
    state = _get(tender, "state") or "India"
    deadline = _get(tender, "bid_end_date")
    value = _get(tender, "value_inr")
    url = _deep_link_for(tender)
    deadline_label, deadline_color = _deadline_display(deadline)
    value_label = _value_display(value)
    return f"""
    <div style="border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:14px;margin:0 0 10px;background:#172033">
      <h3 style="margin:0 0 7px;font-size:15px;line-height:1.35;color:{TEXT}">{escape(str(title))}</h3>
      <p style="margin:0 0 6px;color:{MUTED};font-size:13px;line-height:1.5">{escape(str(organisation))}</p>
      <p style="margin:0 0 6px;color:{MUTED};font-size:13px">
        {escape(str(state))}{' · ' + escape(value_label) if value_label else ''}
      </p>
      <p style="margin:0 0 10px;color:{deadline_color};font-size:13px;font-weight:700">{escape(deadline_label)}</p>
      <a href="{escape(url)}" style="display:inline-block;color:{SAFFRON};font-weight:800;text-decoration:none">View tender</a>
    </div>
    """


def _value_display(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return ""
    if amount <= 0:
        return ""
    if amount >= 10_000_000:
        return f"₹{amount / 10_000_000:.2f} Cr"
    if amount >= 100_000:
        return f"₹{amount / 100_000:.2f} L"
    return f"₹{amount:,.0f}"


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
