"""Files router — upload, list, delete documents with RAG indexing pipeline."""

import os
import json
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.indexing import index_file, remove_file_from_index, reindex_space, search_space

logger = logging.getLogger("contextai.files")
DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai", "spaces")

router = APIRouter()


@router.post("/{space_id}/upload")
async def upload_file_endpoint(space_id: str, file: UploadFile = File(...)):
    """Upload a file to a Space, parse, chunk, and index it."""
    space_dir = os.path.join(DATA_DIR, space_id)
    if not os.path.exists(space_dir):
        raise HTTPException(status_code=404, detail="Space not found")

    raw_dir = os.path.join(space_dir, "raw_files")
    os.makedirs(raw_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(raw_dir, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Index into RAG pipeline
    try:
        index_result = index_file(space_id, file_path)
    except Exception as e:
        logger.error(f"Indexing failed for {file.filename}: {e}")
        index_result = {"status": "error", "error": str(e)}

    # Update meta file count
    _update_meta_counts(space_dir)

    return {
        "status": "uploaded",
        "filename": file.filename,
        "size": len(content),
        "space_id": space_id,
        "indexing": index_result,
    }


@router.get("/{space_id}/files")
async def list_files(space_id: str):
    """List all files in a Space with indexing status."""
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
    """Delete a file from a Space and remove its chunks from the index."""
    file_path = os.path.join(DATA_DIR, space_id, "raw_files", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Remove from index first
    try:
        removal_result = remove_file_from_index(space_id, filename)
    except Exception as e:
        logger.error(f"Index removal failed for {filename}: {e}")
        removal_result = {"status": "error", "error": str(e)}

    # Delete physical file
    os.remove(file_path)

    # Update meta
    space_dir = os.path.join(DATA_DIR, space_id)
    _update_meta_counts(space_dir)

    return {
        "status": "deleted",
        "filename": filename,
        "indexing": removal_result,
    }


@router.post("/{space_id}/reindex")
async def reindex(space_id: str):
    """Rebuild the entire RAG index for a Space from raw files."""
    space_dir = os.path.join(DATA_DIR, space_id)
    if not os.path.exists(space_dir):
        raise HTTPException(status_code=404, detail="Space not found")

    try:
        result = reindex_space(space_id)
    except Exception as e:
        logger.error(f"Reindex failed for space '{space_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return result


@router.post("/{space_id}/search")
async def search(space_id: str, query: str, top_k: int = 5):
    """Search a Space's indexed documents (for testing/debugging)."""
    try:
        results = search_space(space_id, query, top_k=top_k)
    except Exception as e:
        logger.error(f"Search failed for space '{space_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"query": query, "results": results, "count": len(results)}


def _update_meta_counts(space_dir: str):
    """Update the file_count in space meta.json."""
    meta_path = os.path.join(space_dir, "meta.json")
    raw_dir = os.path.join(space_dir, "raw_files")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)
        meta["file_count"] = len(os.listdir(raw_dir)) if os.path.exists(raw_dir) else 0
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
