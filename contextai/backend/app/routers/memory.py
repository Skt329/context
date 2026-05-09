"""Memory router — CRUD for the 4-layer memory system."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.memory_service import (
    get_global_memory,
    set_global_memory,
    append_global_memory,
    get_space_memory,
    set_space_memory,
    append_space_memory,
    get_user_profile,
    set_user_profile,
    auto_update_memory_from_chat,
    build_memory_context,
)

router = APIRouter()


class MemoryContent(BaseModel):
    content: str


class MemoryEntry(BaseModel):
    entry: str


class ChatMessages(BaseModel):
    messages: list[dict]
    space_id: str


# ─── Global Memory ────────────────────────────────────────────

@router.get("/global")
async def get_global():
    """Get global memory content."""
    content = get_global_memory()
    return {"content": content}


@router.put("/global")
async def update_global(body: MemoryContent):
    """Overwrite global memory."""
    set_global_memory(body.content)
    return {"status": "ok", "length": len(body.content)}


@router.post("/global/append")
async def append_to_global(body: MemoryEntry):
    """Append a fact to global memory."""
    append_global_memory(body.entry)
    return {"status": "ok"}


# ─── Space Memory ─────────────────────────────────────────────

@router.get("/space/{space_id}")
async def get_space(space_id: str):
    """Get space-specific memory."""
    content = get_space_memory(space_id)
    return {"content": content, "space_id": space_id}


@router.put("/space/{space_id}")
async def update_space(space_id: str, body: MemoryContent):
    """Overwrite space memory."""
    set_space_memory(space_id, body.content)
    return {"status": "ok", "space_id": space_id, "length": len(body.content)}


@router.post("/space/{space_id}/append")
async def append_to_space(space_id: str, body: MemoryEntry):
    """Append a fact to space memory."""
    append_space_memory(space_id, body.entry)
    return {"status": "ok", "space_id": space_id}


# ─── User Profile (Procedural Memory) ────────────────────────

@router.get("/profile/{space_id}")
async def get_profile(space_id: str):
    """Get user profile for a space."""
    content = get_user_profile(space_id)
    return {"content": content, "space_id": space_id}


@router.put("/profile/{space_id}")
async def update_profile(space_id: str, body: MemoryContent):
    """Overwrite user profile for a space."""
    set_user_profile(space_id, body.content)
    return {"status": "ok", "space_id": space_id, "length": len(body.content)}


# ─── Auto-extraction ──────────────────────────────────────────

@router.post("/extract")
async def extract_from_chat(body: ChatMessages):
    """Extract and store facts from a conversation (uses LLM if available)."""
    count = await auto_update_memory_from_chat(body.messages, body.space_id)
    return {"status": "ok", "facts_extracted": count, "space_id": body.space_id}


# ─── Full Memory Context (for debugging) ─────────────────────

@router.get("/context/{space_id}")
async def get_full_context(space_id: str):
    """Get the full combined memory context that would be injected into the system prompt."""
    context = await build_memory_context(space_id)
    return {"content": context, "space_id": space_id}
