"""Files router — upload and index documents into a Space."""

import os
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai", "spaces")

router = APIRouter()


@router.post("/{space_id}/upload")
async def upload_file(space_id: str, file: UploadFile = File(...)):
    """Upload a file to a Space and trigger indexing."""
    space_dir = os.path.join(DATA_DIR, space_id)
    if not os.path.exists(space_dir):
        raise HTTPException(status_code=404, detail="Space not found")

    raw_dir = os.path.join(space_dir, "raw_files")
    os.makedirs(raw_dir, exist_ok=True)

    file_path = os.path.join(raw_dir, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Update meta file count
    meta_path = os.path.join(space_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)
        meta["file_count"] = len(os.listdir(raw_dir))
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    # TODO: Trigger chunking + contextualization + indexing pipeline
    # 1. Parse file with LlamaIndex SimpleDirectoryReader
    # 2. Chunk with document-type-aware strategy
    # 3. Contextualize each chunk (Anthropic method)
    # 4. Embed and store in ChromaDB
    # 5. Build BM25 index

    return {
        "status": "uploaded",
        "filename": file.filename,
        "size": len(content),
        "space_id": space_id,
    }


@router.get("/{space_id}/files")
async def list_files(space_id: str):
    """List all files in a Space."""
    raw_dir = os.path.join(DATA_DIR, space_id, "raw_files")
    if not os.path.exists(raw_dir):
        return {"files": []}

    files = []
    for entry in os.scandir(raw_dir):
        if entry.is_file():
            files.append({
                "name": entry.name,
                "size": entry.stat().st_size,
                "modified": entry.stat().st_mtime,
            })
    return {"files": files}


@router.delete("/{space_id}/files/{filename}")
async def delete_file(space_id: str, filename: str):
    """Delete a file from a Space and re-index."""
    file_path = os.path.join(DATA_DIR, space_id, "raw_files", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(file_path)

    # Update meta
    meta_path = os.path.join(DATA_DIR, space_id, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)
        raw_dir = os.path.join(DATA_DIR, space_id, "raw_files")
        meta["file_count"] = len(os.listdir(raw_dir))
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    # TODO: Re-index remaining files
    return {"status": "deleted", "filename": filename}
