import asyncio
import logging

from abc import ABC, abstractmethod
from email.message import EmailMessage

import aiosmtplib
import httpx
import msal

from app.core.config import settings



logger = logging.getLogger(__name__)

GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]
GRAPH_SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


class EmailSender(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, html: str) -> None: ...


class SmtpEmailSender(EmailSender):
    async def send(self, to: str, subject: str, html: str) -> None:
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content("Please open this email in an HTML-capable client.")
        message.add_alternative(html, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            # Mailpit has no login and no TLS; a real server (login set) needs STARTTLS
            start_tls=bool(settings.smtp_user),
        )
        logger.info("Email sent via SMTP to %s", to)



class GraphEmailSender(EmailSender):
    def __init__(self) -> None:
        self._app: msal.ConfidentialClientApplication | None = None

    def _get_token(self) -> str:
        if self._app is None:
            self._app = msal.ConfidentialClientApplication(
                client_id=settings.graph_client_id,
                client_credential=settings.graph_client_secret,
                authority=f"https://login.microsoftonline.com/{settings.graph_tenant_id}",
            )
        result = self._app.acquire_token_for_client(scopes=GRAPH_SCOPES)
        if "access_token" not in result:
            raise RuntimeError(
                f"Could not get Graph token: {result.get('error_description', result)}"
            )
        return result["access_token"]

    async def send(self, to: str, subject: str, html: str) -> None:
        token = await asyncio.to_thread(self._get_token)
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": False,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                GRAPH_SEND_MAIL_URL.format(sender=settings.graph_sender),
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        response.raise_for_status()
        logger.info("Email sent via Microsoft Graph to %s", to)


class FallbackEmailSender(EmailSender):
    def __init__(self, primary: EmailSender, fallback: EmailSender) -> None:
        self.primary = primary
        self.fallback = fallback

    async def send(self, to: str, subject: str, html: str) -> None:
        try:
            await self.primary.send(to, subject, html)
        except Exception:
            logger.exception(
                "%s failed, falling back to %s",
                type(self.primary).__name__,
                type(self.fallback).__name__,
            )
            await self.fallback.send(to, subject, html)


def graph_is_configured() -> bool:
    return all(
        [
            settings.graph_tenant_id,
            settings.graph_client_id,
            settings.graph_client_secret,
            settings.graph_sender,
        ]
    )


def get_email_sender() -> EmailSender:
    smtp = SmtpEmailSender()
    if graph_is_configured():
        return FallbackEmailSender(primary=GraphEmailSender(), fallback=smtp)
    return smtp