"""Conversations router — CRUD for persistent chat conversations.

Uses SQLite (via app.db) as the single source of truth.
Frontend hydrates from here.
"""

import json
import re
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import get_db

logger = logging.getLogger("contextai.conversations")

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

def _row_to_convo(row) -> dict:
    """Convert a SQLite Row to conversation dict (camelCase keys for frontend)."""
    return {
        "id": row["id"],
        "spaceId": row["space_id"],
        "title": row["title"],
        "messages": json.loads(row["messages"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _get_last_message_preview(messages_json: str) -> str | None:
    """Get a preview of the last user message for display."""
    try:
        messages = json.loads(messages_json)
    except (json.JSONDecodeError, TypeError):
        return None

    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                clean = re.sub(r"\[Attached:.*?\]", "", content).strip()
                return clean[:120] if clean else None
    return None


# ── Endpoints ────────────────────────────────────────────────

@router.get("")
async def list_conversations(space_id: Optional[str] = Query(None)):
    """List all conversations, optionally filtered by space."""
    conn = get_db()
    try:
        if space_id:
            rows = conn.execute(
                """SELECT id, space_id, title, messages, created_at, updated_at
                   FROM conversations WHERE space_id = ?
                   ORDER BY updated_at DESC""",
                (space_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, space_id, title, messages, created_at, updated_at
                   FROM conversations ORDER BY updated_at DESC"""
            ).fetchall()

        convos = []
        for row in rows:
            messages_json = row["messages"]
            msg_list = json.loads(messages_json) if messages_json else []
            convos.append({
                "id": row["id"],
                "spaceId": row["space_id"],
                "title": row["title"],
                "messageCount": len(msg_list),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "lastMessage": _get_last_message_preview(messages_json),
            })
        return {"conversations": convos}
    finally:
        conn.close()


@router.get("/{convo_id}")
async def get_conversation(convo_id: str):
    """Get a single conversation with full messages."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (convo_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return _row_to_convo(row)
    finally:
        conn.close()


@router.post("")
async def create_conversation(body: ConversationCreate):
    """Create a new empty conversation."""
    import uuid
    now = datetime.utcnow().isoformat()
    convo_id = str(uuid.uuid4())

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO conversations (id, space_id, title, messages, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (convo_id, body.space_id, body.title, "[]", now, now),
        )
        conn.commit()
        logger.info(f"Created conversation {convo_id} for space {body.space_id}")
        return {
            "id": convo_id,
            "spaceId": body.space_id,
            "title": body.title,
            "messages": [],
            "createdAt": now,
            "updatedAt": now,
        }
    finally:
        conn.close()


@router.put("/{convo_id}")
async def update_conversation(convo_id: str, body: ConversationUpdate):
    """Update a conversation (title and/or messages)."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (convo_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        now = datetime.utcnow().isoformat()

        if body.title is not None and body.messages is not None:
            conn.execute(
                "UPDATE conversations SET title = ?, messages = ?, updated_at = ? WHERE id = ?",
                (body.title, json.dumps([m.model_dump() for m in body.messages], ensure_ascii=False), now, convo_id),
            )
        elif body.title is not None:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (body.title, now, convo_id),
            )
        elif body.messages is not None:
            conn.execute(
                "UPDATE conversations SET messages = ?, updated_at = ? WHERE id = ?",
                (json.dumps([m.model_dump() for m in body.messages], ensure_ascii=False), now, convo_id),
            )

        conn.commit()

        # Return updated conversation
        updated = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (convo_id,)
        ).fetchone()
        return _row_to_convo(updated)
    finally:
        conn.close()


@router.delete("/{convo_id}")
async def delete_conversation(convo_id: str):
    """Delete a conversation."""
    conn = get_db()
    try:
        cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (convo_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        logger.info(f"Deleted conversation {convo_id}")
        return {"status": "deleted", "id": convo_id}
    finally:
        conn.close()


@router.delete("")
async def delete_space_conversations(space_id: str = Query(...)):
    """Delete all conversations for a space."""
    conn = get_db()
    try:
        cursor = conn.execute("DELETE FROM conversations WHERE space_id = ?", (space_id,))
        conn.commit()
        deleted = cursor.rowcount
        logger.info(f"Deleted {deleted} conversations for space {space_id}")
        return {"status": "ok", "deleted": deleted, "space_id": space_id}
    finally:
        conn.close()


# ── Bulk Fetch (eliminates N+1 queries) ──────────────────────

@router.post("/bulk")
async def get_conversations_bulk(body: dict):
    """Fetch multiple full conversations in one request."""
    ids = body.get("ids", [])
    if not ids:
        return {"conversations": []}

    conn = get_db()
    try:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM conversations WHERE id IN ({placeholders}) ORDER BY updated_at DESC",
            ids,
        ).fetchall()
        return {"conversations": [_row_to_convo(r) for r in rows]}
    finally:
        conn.close()
