from fastapi import APIRouter, HTTPException, status
from langchain_core.exceptions import ModelError, ModelRateLimitError

from app.ai.chat import run_chat
from app.ai.llm import LLMNotConfiguredError
from app.api.deps import CurrentUser
from app.schemas.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, current_user: CurrentUser):
    try:
        answer, session_id = await run_chat(current_user.id, body.text, body.session_id)
    except ModelRateLimitError:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="the AI assistant is busy, try again in a minute",
        ) from None
    except (ModelError, LLMNotConfiguredError):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the AI assistant is temporarily unavailable",
        ) from None
    return ChatResponse(answer=answer, session_id=session_id)
