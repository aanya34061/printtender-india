import resend

from app.config import get_settings
from app.schemas import TenderRead


async def send_tender_alert(email: str, tenders: list[TenderRead]) -> None:
    settings = get_settings()
    resend.api_key = settings.resend_api_key
    subject = f"{len(tenders)} new printing tender matches"
    html_items = "".join(f"<li><a href='{tender.tender_url or '#'}'>{tender.title}</a></li>" for tender in tenders)
    resend.Emails.send(
        {
            "from": "PrintTender India <alerts@printtender.in>",
            "to": [email],
            "subject": subject,
            "html": f"<h1>PrintTender India</h1><ul>{html_items}</ul>",
        }
    )
