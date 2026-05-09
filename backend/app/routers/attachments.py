"""Attachments router — persist chat image attachments to disk.

Images are saved under ~/.contextai/attachments/{id}.{ext} and served
via a static-file endpoint so conversation JSON files stay lean.
"""

import os
import uuid
import base64
import logging
import mimetypes
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger("contextai.attachments")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai", "attachments")

router = APIRouter()


class AttachmentUpload(BaseModel):
    """Base64-encoded image upload."""
    data_url: str  # "data:image/png;base64,iVBOR..."
    name: str | None = None  # Original filename hint


def _parse_data_url(data_url: str) -> tuple[str, bytes]:
    """Parse a data URL into (mime_type, raw_bytes)."""
    # Format: data:<mime>;base64,<data>
    if not data_url.startswith("data:"):
        raise ValueError("Invalid data URL format")

    header, encoded = data_url.split(",", 1)
    # header = "data:image/png;base64"
    mime_part = header.split(":")[1].split(";")[0]
    raw = base64.b64decode(encoded)
    return mime_part, raw


def _mime_to_ext(mime_type: str) -> str:
    """Convert MIME type to file extension."""
    ext = mimetypes.guess_extension(mime_type)
    if ext:
        return ext  # includes the dot
    # Fallback mapping
    fallback = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    return fallback.get(mime_type, ".bin")


@router.post("/upload")
async def upload_attachment(body: AttachmentUpload):
    """Save a base64 data URL as a file on disk, return a serving URL."""
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        mime_type, raw_bytes = _parse_data_url(body.data_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid data URL: {e}")

    ext = _mime_to_ext(mime_type)
    attachment_id = str(uuid.uuid4())
    filename = f"{attachment_id}{ext}"
    file_path = os.path.join(DATA_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(raw_bytes)

    logger.info(f"Saved attachment {filename} ({len(raw_bytes)} bytes)")

    return {
        "id": attachment_id,
        "filename": filename,
        "url": f"/api/attachments/{filename}",
        "mime_type": mime_type,
        "size": len(raw_bytes),
    }


@router.post("/upload/batch")
async def upload_attachments_batch(body: list[AttachmentUpload]):
    """Upload multiple attachments in one call."""
    os.makedirs(DATA_DIR, exist_ok=True)
    results = []

    for item in body:
        try:
            mime_type, raw_bytes = _parse_data_url(item.data_url)
        except Exception as e:
            results.append({"error": str(e), "name": item.name})
            continue

        ext = _mime_to_ext(mime_type)
        attachment_id = str(uuid.uuid4())
        filename = f"{attachment_id}{ext}"
        file_path = os.path.join(DATA_DIR, filename)

        with open(file_path, "wb") as f:
            f.write(raw_bytes)

        results.append({
            "id": attachment_id,
            "filename": filename,
            "url": f"/api/attachments/{filename}",
            "mime_type": mime_type,
            "size": len(raw_bytes),
            "original_name": item.name,
        })

    logger.info(f"Batch uploaded {len(results)} attachments")
    return {"attachments": results}


@router.get("/{filename}")
async def serve_attachment(filename: str):
    """Serve an attachment file from disk."""
    # Sanitize: prevent directory traversal
    safe_name = os.path.basename(filename)
    file_path = os.path.join(DATA_DIR, safe_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Attachment not found")

    mime_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(
        file_path,
        media_type=mime_type or "application/octet-stream",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )
