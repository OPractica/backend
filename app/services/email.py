import logging
from abc import ABC, abstractmethod
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


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
            start_tls=bool(settings.smtp_user),
        )
        logger.info("Email sent via SMTP to %s", to)


def get_email_sender() -> EmailSender:
    return SmtpEmailSender()
