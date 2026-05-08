"""Spaces router — CRUD for isolated context workspaces."""

import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai", "spaces")

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
    os.makedirs(DATA_DIR, exist_ok=True)
    spaces = []
    for entry in os.scandir(DATA_DIR):
        if entry.is_dir():
            meta_path = os.path.join(entry.path, "meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    spaces.append(json.load(f))
    return {"spaces": spaces}


@router.post("")
async def create_space(space: SpaceCreate):
    """Create a new space with isolated storage."""
    import uuid
    from datetime import datetime

    space_id = str(uuid.uuid4())
    space_dir = os.path.join(DATA_DIR, space_id)
    os.makedirs(space_dir, exist_ok=True)
    os.makedirs(os.path.join(space_dir, "raw_files"), exist_ok=True)
    os.makedirs(os.path.join(space_dir, "chroma_db"), exist_ok=True)
    os.makedirs(os.path.join(space_dir, "bm25_index"), exist_ok=True)

    meta = {
        "id": space_id,
        "name": space.name,
        "icon": space.icon,
        "description": space.description,
        "file_count": 0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    with open(os.path.join(space_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Create empty user profile for procedural memory
    with open(os.path.join(space_dir, "user_profile.md"), "w") as f:
        f.write(f"# {space.name} — User Profile\n\n## Writing Style\n- (auto-populated from feedback)\n\n## Preferences\n- (auto-populated from usage)\n")

    return meta


@router.delete("/{space_id}")
async def delete_space(space_id: str):
    """Delete a space and all its data."""
    import shutil

    space_dir = os.path.join(DATA_DIR, space_id)
    if not os.path.exists(space_dir):
        raise HTTPException(status_code=404, detail="Space not found")
    shutil.rmtree(space_dir)
    return {"status": "deleted", "id": space_id}
