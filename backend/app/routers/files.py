"""Files router — upload, list, delete documents with RAG indexing pipeline."""

import os
import json
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.indexing import index_file, remove_file_from_index, reindex_space, search_space
from app.tasks import task_queue

logger = logging.getLogger("contextai.files")
DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai", "spaces")

router = APIRouter()

# ── Upload constraints ────────────────────────────────────────────
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".csv", ".txt", ".md", ".markdown",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".html", ".xml", ".log", ".ini", ".cfg", ".toml", ".rst",
    ".java", ".cpp", ".c", ".h", ".rs", ".go", ".rb", ".php",
    ".css", ".scss", ".sql", ".sh", ".bat", ".ps1",
}


@router.post("/{space_id}/upload")
async def upload_file_endpoint(space_id: str, file: UploadFile = File(...)):
    """Upload a file to a Space. Indexing runs in background."""
    # Validate file extension
    filename = file.filename or "unnamed"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    space_dir = os.path.join(DATA_DIR, space_id)
    os.makedirs(space_dir, exist_ok=True)

    raw_dir = os.path.join(space_dir, "raw_files")
    os.makedirs(raw_dir, exist_ok=True)

    # Read with size limit
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // 1024 // 1024} MB). Maximum allowed: {MAX_FILE_SIZE // 1024 // 1024} MB",
        )

    # Save file immediately (non-blocking)
    file_path = os.path.join(raw_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Enqueue indexing as a background task
    task_id = str(uuid.uuid4())
    await task_queue.enqueue(task_id, index_file(space_id, file_path))

    # Update meta file count
    _update_meta_counts(space_dir)

    return {
        "status": "uploaded",
        "filename": file.filename,
        "size": len(content),
        "space_id": space_id,
        "indexing": {"status": "queued", "task_id": task_id},
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
        result = await reindex_space(space_id)
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
