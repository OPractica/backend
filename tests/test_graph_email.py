import httpx
import pytest

from app.services import email as email_module
from app.services.email import (
    EmailSender,
    FallbackEmailSender,
    GraphEmailSender,
    SmtpEmailSender,
    get_email_sender,
)

pytestmark = pytest.mark.anyio

GRAPH_SETTINGS = (
    "graph_tenant_id",
    "graph_client_id",
    "graph_client_secret",
    "graph_sender",
)


class FakeSender(EmailSender):
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, html: str) -> None:
        if self.fail:
            raise RuntimeError("boom")
        self.sent.append((to, subject, html))


async def test_graph_sender_builds_send_mail_request(monkeypatch: pytest.MonkeyPatch):
    calls = {}

    async def fake_post(self, url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return httpx.Response(202, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(GraphEmailSender, "_get_token", lambda self: "fake-token")
    monkeypatch.setattr(email_module.settings, "graph_sender", "sender@example.com")

    await GraphEmailSender().send("user@example.com", "Hello", "<p>Hi</p>")

    assert calls["url"] == (
        "https://graph.microsoft.com/v1.0/users/sender@example.com/sendMail"
    )
    assert calls["kwargs"]["headers"]["Authorization"] == "Bearer fake-token"
    message = calls["kwargs"]["json"]["message"]
    assert message["subject"] == "Hello"
    assert message["body"] == {"contentType": "HTML", "content": "<p>Hi</p>"}
    assert message["toRecipients"] == [
        {"emailAddress": {"address": "user@example.com"}}
    ]


async def test_fallback_uses_primary_when_it_works():
    primary, fallback = FakeSender(), FakeSender()

    await FallbackEmailSender(primary, fallback).send("a@example.com", "Hi", "<p>x</p>")

    assert len(primary.sent) == 1
    assert fallback.sent == []


async def test_fallback_used_when_primary_fails():
    primary, fallback = FakeSender(fail=True), FakeSender()

    await FallbackEmailSender(primary, fallback).send("a@example.com", "Hi", "<p>x</p>")

    assert primary.sent == []
    assert len(fallback.sent) == 1


async def test_smtp_used_when_graph_not_configured(monkeypatch: pytest.MonkeyPatch):
    for name in GRAPH_SETTINGS:
        monkeypatch.setattr(email_module.settings, name, "")

    assert isinstance(get_email_sender(), SmtpEmailSender)


async def test_graph_with_fallback_used_when_graph_configured(
    monkeypatch: pytest.MonkeyPatch,
):
    for name in GRAPH_SETTINGS:
        monkeypatch.setattr(email_module.settings, name, "value")

    assert isinstance(get_email_sender(), FallbackEmailSender)
