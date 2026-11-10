from typing import Annotated

from fastapi import APIRouter, Body, status
from langchain_core.exceptions import ModelError, ModelRateLimitError

from app.ai.chat import run_chat
from app.ai.llm import LLMNotConfiguredError
from app.api.deps import CurrentUser
from app.api.errors import APIError
from app.api.openapi import (
    AUTH_RESPONSES,
    error_response,
    example_response,
)
from app.schemas.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with the booking assistant",
    description=(
        "Sends a text message to the AI assistant, which can find free seats and "
        "book or cancel them. Pass the `session_id` from the previous answer to "
        "continue the same conversation."
    ),
    responses={
        200: example_response(
            "The assistant answer",
            {
                "answer": "Seat A-01 is free tomorrow from 09:00 to 13:00. Book it?",
                "session_id": "5f0c1c1e-8f7a-4b0e-9d0b-2a7c3a6f9e11",
            },
        ),
        429: error_response(
            "The AI provider rate limit is reached",
            "the AI assistant is busy, try again in a minute",
            "ai_busy",
        ),
        503: error_response(
            "The AI assistant is not configured or the provider failed",
            "the AI assistant is temporarily unavailable",
            "ai_unavailable",
        ),
        **AUTH_RESPONSES,
    },
)
async def chat(
    body: Annotated[
        ChatRequest,
        Body(
            openapi_examples={
                "new_conversation": {
                    "summary": "Start a conversation",
                    "value": {"text": "Find me a free seat tomorrow morning"},
                },
                "follow_up": {
                    "summary": "Continue a conversation",
                    "value": {
                        "text": "Yes, book it",
                        "session_id": "5f0c1c1e-8f7a-4b0e-9d0b-2a7c3a6f9e11",
                    },
                },
            }
        ),
    ],
    current_user: CurrentUser,
):
    try:
        answer, session_id = await run_chat(current_user.id, body.text, body.session_id)
    except ModelRateLimitError:
        raise APIError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="the AI assistant is busy, try again in a minute",
            code="ai_busy",
        ) from None
    except (ModelError, LLMNotConfiguredError):
        raise APIError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the AI assistant is temporarily unavailable",
            code="ai_unavailable",
        ) from None
    return ChatResponse(answer=answer, session_id=session_id)
