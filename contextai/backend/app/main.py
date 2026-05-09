"""
ContextAI Backend — FastAPI server for RAG, Memory, LLM routing, and Screen Context.
Runs as a Tauri sidecar process on localhost:8742.
"""

import os
import sys
import json
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, spaces, files, settings, context, memory, conversations, attachments

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("contextai")

# Data directory
DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")


def ensure_data_dirs():
    """Create the data directory structure on first run."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "spaces"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "conversations"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "attachments"), exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"providers": {}, "preferences": {}}, f, indent=2)
        logger.info(f"Created settings file at {SETTINGS_FILE}")

    # Create default General space if none exist
    spaces_dir = os.path.join(DATA_DIR, "spaces")
    if not any(os.scandir(spaces_dir)):
        default_id = "default"
        default_dir = os.path.join(spaces_dir, default_id)
        os.makedirs(default_dir, exist_ok=True)
        os.makedirs(os.path.join(default_dir, "raw_files"), exist_ok=True)
        os.makedirs(os.path.join(default_dir, "chroma_db"), exist_ok=True)
        os.makedirs(os.path.join(default_dir, "bm25_index"), exist_ok=True)
        meta = {
            "id": default_id,
            "name": "General",
            "icon": "🌐",
            "description": "Default workspace for general tasks",
            "file_count": 0,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        with open(os.path.join(default_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        with open(os.path.join(default_dir, "user_profile.md"), "w") as f:
            f.write("# General — User Profile\n\n## Writing Style\n- (auto-populated)\n\n## Preferences\n- (auto-populated)\n")
        logger.info("Created default General space")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    ensure_data_dirs()
    logger.info(f"ContextAI backend started — data dir: {DATA_DIR}")
    yield
    logger.info("ContextAI backend shutting down")


app = FastAPI(
    title="ContextAI Backend",
    version="0.1.0",
    description="Personal context engine — RAG, Memory, Multi-provider LLM",
    lifespan=lifespan,
)

# CORS — allow Tauri WebView and localhost dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:8742",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(spaces.router, prefix="/api/spaces", tags=["Spaces"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(context.router, prefix="/api/context", tags=["Context"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])
app.include_router(attachments.router, prefix="/api/attachments", tags=["Attachments"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "data_dir": DATA_DIR}


def main():
    """Entry point for the sidecar process."""
    port = int(os.environ.get("CONTEXTAI_PORT", "8742"))
    logger.info(f"Starting ContextAI backend on port {port}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
