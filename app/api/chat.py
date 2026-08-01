import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import require_workspace_user
from app.schemas.chat import ChatHistoryResponse, ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.auth_service import AuthenticatedUser

router = APIRouter(prefix="/api", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user: AuthenticatedUser = Depends(require_workspace_user)):
    try:
        return ChatResponse(answer=ChatService.chat(request.message, owner_id=user.id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="Local chat model is unavailable. Please try again.") from error


def _sse(event: str, payload: dict[str, str]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def stream_chat(request: ChatRequest, user: AuthenticatedUser = Depends(require_workspace_user)):
    """SSE endpoint used by the voice conversation UI for low-latency replies."""
    def events() -> Iterator[str]:
        try:
            for chunk in ChatService.stream(request.message, owner_id=user.id):
                yield _sse("delta", {"type": "delta", "delta": chunk})
            yield _sse("done", {"type": "done"})
        except ValueError as error:
            yield _sse("error", {"type": "error", "detail": str(error)})
        except Exception:
            yield _sse("error", {"type": "error", "detail": "Local chat model is unavailable. Please try again."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Content-Encoding": "identity",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history", response_model=ChatHistoryResponse)
def chat_history(user: AuthenticatedUser = Depends(require_workspace_user)):
    return ChatHistoryResponse(messages=ChatService.history(user.id))
