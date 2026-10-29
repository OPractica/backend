import pytest

from app.services import email as email_module
from app.services.email import SmtpEmailSender

pytestmark = pytest.mark.anyio


async def test_smtp_sender_builds_html_message(monkeypatch: pytest.MonkeyPatch):
    sent = {}

    async def fake_send(message, **kwargs):
        sent["message"] = message
        sent["kwargs"] = kwargs

    monkeypatch.setattr(email_module.aiosmtplib, "send", fake_send)

    await SmtpEmailSender().send("user@example.com", "Hello", "<p>Hi</p>")

    message = sent["message"]
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Hello"
    assert "<p>Hi</p>" in message.get_body(preferencelist=("html",)).get_content()
    assert sent["kwargs"]["hostname"] == email_module.settings.smtp_host
