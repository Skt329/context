"""Chat router — streaming AI responses with RAG context injection."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    space_id: str
    screen_context: str | None = None


class RateRequest(BaseModel):
    message_id: str
    rating: int  # 1-5


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream an AI response with RAG context from the active Space."""
    
    async def generate():
        # TODO: Wire up LiteLLM + RAG pipeline
        # 1. Retrieve relevant chunks from Space's ChromaDB + BM25
        # 2. Rerank with FlashRank
        # 3. Build system prompt with user_profile.md + retrieved chunks
        # 4. Stream response via LiteLLM
        response = f"[ContextAI] Received: '{request.message}' in space '{request.space_id}'"
        for char in response:
            yield f"data: {char}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/rate")
async def rate_message(request: RateRequest):
    """Rate a message to update procedural memory."""
    # TODO: Update user_profile.md based on rating
    return {"status": "ok", "message_id": request.message_id, "rating": request.rating}
