from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.services.voice.upload import MAX_AUDIO_BYTES

VOICE_MAX_BODY_BYTES = MAX_AUDIO_BYTES + 1_000_000
VOICE_PATH = "/api/v1/voice/transcribe"


class VoiceBodyLimitMiddleware:
    """Apply a request size limit only to the voice upload endpoint."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.limited_app = RequestBodyLimitMiddleware(
            app,
            max_body_size=VOICE_MAX_BODY_BYTES,
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == VOICE_PATH
        ):
            await self.limited_app(scope, receive, send)
            return

        await self.app(scope, receive, send)
