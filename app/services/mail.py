import asyncio
import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

from app.core.config import settings
from app.utils import local_tz, utc

log = logging.getLogger("mail")


def _send(msg: EmailMessage) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
        if settings.smtp_tls:
            s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)


async def send_mail(to: str, subject: str, body: str, strict: bool = False) -> None:
    """Send an email. strict=True raises on failure (used for the confirmation code)."""
    if not settings.smtp_host:
        log.warning("SMTP is not configured, printing the email instead.\nTO: %s\nSUBJECT: %s\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    msg.set_content(body)
    try:
        await asyncio.to_thread(_send, msg)
    except Exception:
        log.exception("Could not send mail to %s", to)
        if strict:
            raise


def when(starts: datetime, ends: datetime) -> tuple[str, str]:
    s, e = utc(starts).astimezone(local_tz()), utc(ends).astimezone(local_tz())
    return s.strftime("%A, %d %B %Y"), f"{s:%H:%M}-{e:%H:%M} ({settings.office_tz})"


def code_email(code: str) -> tuple[str, str]:
    return (
        "Your Workplace Booking confirmation code",
        f"Your confirmation code is: {code}\n\nIt expires in {settings.code_ttl_minutes} minutes.\n"
        "If you did not try to register, you can ignore this email.",
    )


def booking_email(name: str, seat: str, starts: datetime, ends: datetime, cancelled: bool = False) -> tuple[str, str]:
    day, hours = when(starts, ends)
    if cancelled:
        return (
            f"Booking cancelled: {seat}, {day}",
            f"Hi {name},\n\nYour booking was cancelled.\n\nSeat: {seat}\nDate: {day}\nTime: {hours}\n",
        )
    return (
        f"Booking confirmed: {seat}, {day}, {hours}",
        f"Hi {name},\n\nYour seat is booked.\n\nSeat: {seat}\nDate: {day}\nTime: {hours}\n"
        "Office: Zity Mall, 7th floor, Orange kITchen\n\nYou can cancel from your profile page.",
    )
