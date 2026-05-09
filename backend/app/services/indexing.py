"""Indexing pipeline — orchestrates file parsing, chunking, and RAG indexing.

Flow: File Upload → Parse → Detect Type → Chunk → Index (ChromaDB + BM25)
"""

import os
import logging

from app.services.parser import parse_file, detect_document_type
from app.services.chunking import chunk_document
from app.services.rag_service import SpaceIndex, make_chunk_id

logger = logging.getLogger("contextai.indexing")

# Cache SpaceIndex instances to avoid re-initialization
_index_cache: dict[str, SpaceIndex] = {}


def get_space_index(space_id: str) -> SpaceIndex:
    """Get or create a SpaceIndex for the given space."""
    if space_id not in _index_cache:
        _index_cache[space_id] = SpaceIndex(space_id)
    return _index_cache[space_id]


async def index_file(space_id: str, file_path: str) -> dict:
    """Parse, chunk, contextualize, and index a single file into a Space's RAG index.
    
    Returns:
        Dict with indexing results: chunks_created, doc_type, etc.
    """
    filename = os.path.basename(file_path)
    logger.info(f"Indexing '{filename}' into space '{space_id}'")

    # 1. Parse file to raw text
    text = parse_file(file_path)
    if not text or len(text.strip()) < 50:
        logger.warning(f"File '{filename}' yielded too little text ({len(text)} chars)")
        return {
            "status": "skipped",
            "filename": filename,
            "reason": "Insufficient text content",
            "chars": len(text),
        }

    # 2. Detect document type
    doc_type = detect_document_type(filename, text)
    logger.info(f"Detected document type for '{filename}': {doc_type}")

    # 3. Chunk document
    chunks = chunk_document(text, doc_type, filename)
    if not chunks:
        return {
            "status": "skipped",
            "filename": filename,
            "reason": "No chunks produced",
            "doc_type": doc_type,
        }

    # 3.5 Contextual chunking (if LLM available)
    try:
        from app.services.chunking import contextualize_chunks
        chunks = await contextualize_chunks(chunks, text)
    except Exception as e:
        logger.debug(f"Contextual chunking skipped: {e}")

    # 4. Build chunk dicts for indexing
    chunk_dicts = []
    for chunk in chunks:
        chunk_id = make_chunk_id(filename, chunk.index)
        chunk_dicts.append({
            "id": chunk_id,
            "text": chunk.final_text,
            "source_file": filename,
            "doc_type": doc_type,
            "index": chunk.index,
        })

    # 5. Index into ChromaDB + BM25
    index = get_space_index(space_id)
    index.index_chunks(chunk_dicts)

    result = {
        "status": "indexed",
        "filename": filename,
        "doc_type": doc_type,
        "chunks_created": len(chunk_dicts),
        "total_chars": len(text),
        "total_chunks_in_space": index.chunk_count,
        "contextualized": sum(1 for c in chunks if c.contextualized_text),
    }
    logger.info(f"Indexed '{filename}': {len(chunk_dicts)} chunks ({doc_type})")
    return result


def remove_file_from_index(space_id: str, filename: str) -> dict:
    """Remove a file's chunks from the Space index.
    
    Returns:
        Dict with removal results.
    """
    index = get_space_index(space_id)
    index.remove_file_chunks(filename)
    return {
        "status": "removed",
        "filename": filename,
        "remaining_chunks": index.chunk_count,
    }


async def reindex_space(space_id: str) -> dict:
    """Rebuild the entire index for a Space from its raw files.
    
    Clears existing indices and re-indexes all files in raw_files/.
    """
    DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai", "spaces")
    raw_dir = os.path.join(DATA_DIR, space_id, "raw_files")

    if not os.path.exists(raw_dir):
        return {"status": "error", "reason": "raw_files directory not found"}

    # Clear existing index
    index = get_space_index(space_id)
    index.clear_all()

    # Re-index all files
    results = []
    for entry in os.scandir(raw_dir):
        if entry.is_file():
            result = await index_file(space_id, entry.path)
            results.append(result)

    total_chunks = sum(r.get("chunks_created", 0) for r in results)
    logger.info(f"Reindexed space '{space_id}': {len(results)} files, {total_chunks} chunks")

    return {
        "status": "reindexed",
        "space_id": space_id,
        "files_processed": len(results),
        "total_chunks": total_chunks,
        "details": results,
    }


def search_space(space_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Search a Space's index using hybrid retrieval.
    
    Returns top_k chunks with text, source_file, doc_type, and scores.
    """
    index = get_space_index(space_id)
    return index.search(query, top_k=top_k)
