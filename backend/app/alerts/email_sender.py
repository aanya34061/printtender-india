import resend

from app.config import get_settings
from app.schemas import TenderRead

FROM_ADDRESS = "PrintTender India <alerts@printtender.in>"


def _configure() -> None:
    resend.api_key = get_settings().RESEND_API_KEY


def send_confirmation_email(to_email: str, keyword: str, confirm_url: str) -> None:
    _configure()
    resend.Emails.send(
        {
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": "Confirm your PrintTender India alert",
            "html": f"""
            <h2>Confirm your tender alert</h2>
            <p>You subscribed to alerts for: <strong>{keyword}</strong></p>
            <p>Click the button below to confirm your subscription:</p>
            <p>
              <a href="{confirm_url}"
                 style="display:inline-block;padding:12px 24px;background:#C0392B;
                        color:white;font-weight:bold;border-radius:8px;text-decoration:none">
                Confirm Subscription
              </a>
            </p>
            <p style="font-size:12px;color:#999">If you didn't sign up, ignore this email.</p>
            """,
        }
    )


def send_welcome_email(to_email: str, keywords: list[str], frequency: str) -> None:
    _configure()
    kw_list = ", ".join(keywords)
    resend.Emails.send(
        {
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": "Welcome to PrintTender India Alerts",
            "text": (
                f"You have subscribed to {frequency} alerts for: {kw_list}.\n\n"
                "You will receive tender alerts matching your keywords.\n"
                "PrintTender India Team"
            ),
        }
    )


def send_daily_digest(to_email: str, tenders: list[TenderRead]) -> None:
    _configure()
    top = tenders[:20]
    rows = "".join(
        f"""<tr>
          <td><a href="{t.portal_url or '#'}">{t.title}</a></td>
          <td>{t.organisation or '—'}</td>
          <td>{t.state or '—'}</td>
          <td>{t.bid_end_date.strftime('%d %b %Y') if t.bid_end_date else '—'}</td>
        </tr>"""
        for t in top
    )
    resend.Emails.send(
        {
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": f"PrintTender Daily Digest — {len(top)} tenders",
            "html": f"""
            <h2>PrintTender India — Daily Digest</h2>
            <p>{len(top)} active printing tenders:</p>
            <table border="1" cellpadding="6" cellspacing="0">
              <thead><tr><th>Title</th><th>Organisation</th><th>State</th><th>Deadline</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
            """,
        }
    )


def send_urgent_alert(to_email: str, tender: TenderRead) -> None:
    _configure()
    deadline = tender.bid_end_date.strftime("%d %b %Y %H:%M") if tender.bid_end_date else "soon"
    resend.Emails.send(
        {
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": f"URGENT: {tender.title[:60]} closing {deadline}",
            "html": f"""
            <h2>⚠️ Tender Closing Within 72 Hours</h2>
            <p><strong>{tender.title}</strong></p>
            <p>Organisation: {tender.organisation or '—'}</p>
            <p>Deadline: <strong>{deadline}</strong></p>
            <p><a href="{tender.portal_url or '#'}">View Tender</a></p>
            """,
        }
    )
