"""Spaces router — CRUD for isolated context workspaces.

Space metadata lives in SQLite (via app.db).
Raw files, ChromaDB, and BM25 indexes remain on the filesystem
because they are binary stores managed by their respective libraries.
"""

import json
import os
import uuid
import shutil
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_db

logger = logging.getLogger("contextai.spaces")

SPACES_DIR = os.path.join(os.path.expanduser("~"), ".contextai", "spaces")

router = APIRouter()


class SpaceCreate(BaseModel):
    name: str
    icon: str = "📁"
    description: str = ""


class SpaceUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    description: str | None = None


@router.get("")
async def list_spaces():
    """List all spaces."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM spaces ORDER BY created_at ASC"
        ).fetchall()
        return {"spaces": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("")
async def create_space(space: SpaceCreate):
    """Create a new space with isolated storage."""
    space_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Create filesystem directories for binary stores
    space_dir = os.path.join(SPACES_DIR, space_id)
    os.makedirs(space_dir, exist_ok=True)
    os.makedirs(os.path.join(space_dir, "raw_files"), exist_ok=True)
    os.makedirs(os.path.join(space_dir, "chroma_db"), exist_ok=True)
    os.makedirs(os.path.join(space_dir, "bm25_index"), exist_ok=True)

    # Insert into SQLite
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO spaces (id, name, icon, description, file_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (space_id, space.name, space.icon, space.description, 0, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    meta = {
        "id": space_id,
        "name": space.name,
        "icon": space.icon,
        "description": space.description,
        "file_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    logger.info(f"Created space '{space.name}' ({space_id})")
    return meta


@router.put("/{space_id}")
async def update_space(space_id: str, body: SpaceUpdate):
    """Update a space's metadata."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Space not found")

        now = datetime.utcnow().isoformat()
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.icon is not None:
            updates["icon"] = body.icon
        if body.description is not None:
            updates["description"] = body.description

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [now, space_id]
            conn.execute(
                f"UPDATE spaces SET {set_clause}, updated_at = ? WHERE id = ?",
                values,
            )
            conn.commit()

        # Return updated
        updated = conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
        return dict(updated)
    finally:
        conn.close()


@router.get("/{space_id}/file-count")
async def get_file_count(space_id: str):
    """Get the actual file count for a space from disk."""
    raw_dir = os.path.join(SPACES_DIR, space_id, "raw_files")
    if not os.path.exists(raw_dir):
        return {"count": 0}
    count = sum(1 for f in os.scandir(raw_dir) if f.is_file())
    return {"count": count}


@router.delete("/{space_id}")
async def delete_space(space_id: str):
    """Delete a space and all its data (DB + filesystem)."""
    conn = get_db()
    try:
        cursor = conn.execute("DELETE FROM spaces WHERE id = ?", (space_id,))
        # Also delete conversations and memory for this space
        conn.execute("DELETE FROM conversations WHERE space_id = ?", (space_id,))
        conn.execute("DELETE FROM memory WHERE space_id = ?", (space_id,))
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Space not found")
    finally:
        conn.close()

    # Remove filesystem data (raw files, chroma, bm25)
    space_dir = os.path.join(SPACES_DIR, space_id)
    if os.path.exists(space_dir):
        shutil.rmtree(space_dir)

    logger.info(f"Deleted space {space_id}")
    return {"status": "deleted", "id": space_id}
