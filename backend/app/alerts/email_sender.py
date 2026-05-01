import resend

from app.config import get_settings
from app.schemas import TenderRead


def _configure() -> None:
    resend.api_key = get_settings().RESEND_API_KEY


FROM_ADDRESS = "PrintTender India <alerts@printtender.in>"


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
                "To unsubscribe, reply to this email.\n\n"
                "PrintTender India Team"
            ),
        }
    )


def send_daily_digest(to_email: str, tenders: list[TenderRead]) -> None:
    _configure()
    top = tenders[:20]
    rows = "".join(
        f"""
        <tr>
          <td><a href="{t.portal_url or '#'}">{t.title}</a></td>
          <td>{t.organisation or '—'}</td>
          <td>{t.state or '—'}</td>
          <td>{t.bid_end_date.strftime('%d %b %Y') if t.bid_end_date else '—'}</td>
          <td><a href="{t.portal_url or '#'}">View</a></td>
        </tr>"""
        for t in top
    )
    html = f"""
    <h2>PrintTender India — Daily Digest</h2>
    <p>{len(top)} active printing tenders for you:</p>
    <table border="1" cellpadding="6" cellspacing="0">
      <thead>
        <tr><th>Title</th><th>Organisation</th><th>State</th><th>Deadline</th><th>Link</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p style="font-size:12px;color:#999;">PrintTender India — Free Printing Tender Alerts</p>
    """
    resend.Emails.send(
        {
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": f"PrintTender Daily Digest — {len(top)} tenders",
            "html": html,
        }
    )


def send_urgent_alert(to_email: str, tender: TenderRead) -> None:
    _configure()
    deadline = tender.bid_end_date.strftime("%d %b %Y %H:%M") if tender.bid_end_date else "soon"
    html = f"""
    <h2>⚠️ Urgent: Tender Closing Within 72 Hours</h2>
    <p><strong>{tender.title}</strong></p>
    <p>Organisation: {tender.organisation or '—'}</p>
    <p>State: {tender.state or '—'}</p>
    <p>Deadline: <strong>{deadline}</strong></p>
    <p><a href="{tender.portal_url or '#'}">View Tender &rarr;</a></p>
    <p style="font-size:12px;color:#999;">PrintTender India</p>
    """
    resend.Emails.send(
        {
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": f"URGENT: {tender.title[:60]} closing {deadline}",
            "html": html,
        }
    )
