"""
ContextAI Backend — FastAPI server for RAG, Memory, LLM routing, and Screen Context.
Runs as a Tauri sidecar process on localhost.
"""

import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, spaces, files, settings, context

# Determine data directory
DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai")
os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI(
    title="ContextAI Backend",
    version="0.1.0",
    description="Personal context engine — RAG, Memory, Multi-provider LLM",
)

# CORS for Tauri WebView
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tauri uses custom protocol
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(spaces.router, prefix="/api/spaces", tags=["Spaces"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(context.router, prefix="/api/context", tags=["Context"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


def main():
    """Entry point for the sidecar process."""
    port = int(os.environ.get("CONTEXTAI_PORT", "8742"))
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
