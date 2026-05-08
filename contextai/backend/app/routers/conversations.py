"""Conversations router — CRUD for persistent chat conversations.

Stores conversations as JSON files under ~/.contextai/conversations/{id}.json
This is the single source of truth — frontend hydrates from here.
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("contextai.conversations")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai", "conversations")

router = APIRouter()


# ── Models ───────────────────────────────────────────────────

class MessageModel(BaseModel):
    id: str
    role: str  # 'user' | 'assistant'
    content: str
    timestamp: str
    attachments: list[dict] | None = None


class ConversationCreate(BaseModel):
    space_id: str
    title: str = "New Chat"


class ConversationUpdate(BaseModel):
    title: str | None = None
    messages: list[MessageModel] | None = None


class ConversationResponse(BaseModel):
    id: str
    spaceId: str
    title: str
    messages: list[dict]
    createdAt: str
    updatedAt: str


# ── Helpers ──────────────────────────────────────────────────

def _convo_path(convo_id: str) -> str:
    return os.path.join(DATA_DIR, f"{convo_id}.json")


def _read_convo(convo_id: str) -> dict | None:
    path = _convo_path(convo_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read conversation {convo_id}: {e}")
        return None


def _write_convo(convo: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _convo_path(convo["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(convo, f, indent=2, ensure_ascii=False)


def _list_all_convos() -> list[dict]:
    """List all conversations, returning metadata without full message bodies."""
    os.makedirs(DATA_DIR, exist_ok=True)
    convos = []
    for entry in os.scandir(DATA_DIR):
        if entry.name.endswith(".json") and entry.is_file():
            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Return lightweight summary (no full messages)
                    convos.append({
                        "id": data["id"],
                        "spaceId": data.get("spaceId", "default"),
                        "title": data.get("title", "New Chat"),
                        "messageCount": len(data.get("messages", [])),
                        "createdAt": data.get("createdAt", ""),
                        "updatedAt": data.get("updatedAt", ""),
                        "lastMessage": _get_last_message_preview(data.get("messages", [])),
                    })
            except Exception as e:
                logger.warning(f"Skipping corrupt conversation file {entry.name}: {e}")
    # Sort newest first
    convos.sort(key=lambda c: c.get("updatedAt", ""), reverse=True)
    return convos


def _get_last_message_preview(messages: list[dict]) -> str | None:
    """Get a preview of the last user message for display."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                # Strip attachment markers
                import re
                clean = re.sub(r"\[Attached:.*?\]", "", content).strip()
                return clean[:120] if clean else None
    return None


# ── Endpoints ────────────────────────────────────────────────

@router.get("")
async def list_conversations(space_id: Optional[str] = Query(None)):
    """List all conversations, optionally filtered by space."""
    convos = _list_all_convos()
    if space_id:
        convos = [c for c in convos if c.get("spaceId") == space_id]
    return {"conversations": convos}


@router.get("/{convo_id}")
async def get_conversation(convo_id: str):
    """Get a single conversation with full messages."""
    convo = _read_convo(convo_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.post("")
async def create_conversation(body: ConversationCreate):
    """Create a new empty conversation."""
    import uuid
    now = datetime.utcnow().isoformat()
    convo = {
        "id": str(uuid.uuid4()),
        "spaceId": body.space_id,
        "title": body.title,
        "messages": [],
        "createdAt": now,
        "updatedAt": now,
    }
    _write_convo(convo)
    logger.info(f"Created conversation {convo['id']} for space {body.space_id}")
    return convo


@router.put("/{convo_id}")
async def update_conversation(convo_id: str, body: ConversationUpdate):
    """Update a conversation (title and/or messages)."""
    convo = _read_convo(convo_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if body.title is not None:
        convo["title"] = body.title
    if body.messages is not None:
        convo["messages"] = [m.model_dump() for m in body.messages]
    convo["updatedAt"] = datetime.utcnow().isoformat()

    _write_convo(convo)
    return convo


@router.delete("/{convo_id}")
async def delete_conversation(convo_id: str):
    """Delete a conversation."""
    path = _convo_path(convo_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Conversation not found")
    os.remove(path)
    logger.info(f"Deleted conversation {convo_id}")
    return {"status": "deleted", "id": convo_id}


@router.delete("")
async def delete_space_conversations(space_id: str = Query(...)):
    """Delete all conversations for a space."""
    deleted = 0
    os.makedirs(DATA_DIR, exist_ok=True)
    for entry in os.scandir(DATA_DIR):
        if entry.name.endswith(".json") and entry.is_file():
            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("spaceId") == space_id:
                    os.remove(entry.path)
                    deleted += 1
            except Exception:
                pass
    logger.info(f"Deleted {deleted} conversations for space {space_id}")
    return {"status": "ok", "deleted": deleted, "space_id": space_id}
