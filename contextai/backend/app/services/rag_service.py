"""RAG Service — Hybrid retrieval with ChromaDB (vector) + BM25S (keyword) + FlashRank (reranker).

Implements the full pipeline:
  Query → [BM25 top-50] + [ChromaDB top-50] → RRF fusion → FlashRank rerank → top-5 chunks
"""

import os
import json
import logging
import hashlib
import pickle
from typing import Optional

import chromadb
import bm25s
import numpy as np

logger = logging.getLogger("contextai.rag")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai")

# Global FlashRank reranker (loaded once)
_reranker = None


def _get_reranker():
    """Lazy-load FlashRank reranker (downloads model on first use)."""
    global _reranker
    if _reranker is None:
        from flashrank import Ranker
        _reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir=os.path.join(DATA_DIR, "models"))
        logger.info("FlashRank reranker loaded")
    return _reranker


class SpaceIndex:
    """Manages the ChromaDB + BM25 index for a single Space."""

    def __init__(self, space_id: str):
        self.space_id = space_id
        self.space_dir = os.path.join(DATA_DIR, "spaces", space_id)
        self.chroma_dir = os.path.join(self.space_dir, "chroma_db")
        self.bm25_dir = os.path.join(self.space_dir, "bm25_index")
        self.chunks_file = os.path.join(self.space_dir, "chunks.json")

        os.makedirs(self.chroma_dir, exist_ok=True)
        os.makedirs(self.bm25_dir, exist_ok=True)

        # ChromaDB client (persistent, per-space)
        self._chroma_client = chromadb.PersistentClient(path=self.chroma_dir)
        self._collection = self._chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

        # BM25 index
        self._bm25: Optional[bm25s.BM25] = None
        self._bm25_corpus: list[str] = []
        self._load_bm25()

        # Chunk metadata (maps chunk_id → source info)
        self._chunks_meta: dict[str, dict] = {}
        self._load_chunks_meta()

    # ── Indexing ──────────────────────────────────────────────────

    def index_chunks(self, chunks: list[dict]):
        """Index a batch of chunks into both ChromaDB and BM25.
        
        Each chunk dict must have:
          - id: unique chunk ID
          - text: the chunk text (contextualized if available)
          - source_file: original filename
          - doc_type: document type
          - index: chunk position in document
        """
        if not chunks:
            return

        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            chunk_id = chunk["id"]
            text = chunk["text"]
            ids.append(chunk_id)
            documents.append(text)
            metadatas.append({
                "source_file": chunk.get("source_file", ""),
                "doc_type": chunk.get("doc_type", "general"),
                "chunk_index": chunk.get("index", 0),
            })
            self._chunks_meta[chunk_id] = {
                "text": text,
                "source_file": chunk.get("source_file", ""),
                "doc_type": chunk.get("doc_type", "general"),
                "index": chunk.get("index", 0),
            }

        # Upsert into ChromaDB (uses default embedding function)
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"Indexed {len(ids)} chunks into ChromaDB for space '{self.space_id}'")

        # Rebuild BM25 index
        self._rebuild_bm25()

        # Save chunk metadata
        self._save_chunks_meta()

    def remove_file_chunks(self, source_file: str):
        """Remove all chunks from a specific file and re-index BM25."""
        # Find chunk IDs for this file
        ids_to_remove = [
            cid for cid, meta in self._chunks_meta.items()
            if meta.get("source_file") == source_file
        ]

        if not ids_to_remove:
            return

        # Remove from ChromaDB
        self._collection.delete(ids=ids_to_remove)

        # Remove from metadata
        for cid in ids_to_remove:
            del self._chunks_meta[cid]

        # Rebuild BM25
        self._rebuild_bm25()
        self._save_chunks_meta()

        logger.info(f"Removed {len(ids_to_remove)} chunks for '{source_file}' from space '{self.space_id}'")

    def clear_all(self):
        """Clear all indices for this space."""
        self._chroma_client.delete_collection("documents")
        self._collection = self._chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        self._chunks_meta.clear()
        self._bm25 = None
        self._bm25_corpus = []
        self._save_chunks_meta()
        logger.info(f"Cleared all indices for space '{self.space_id}'")

    # ── Retrieval ─────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Hybrid search: BM25 + ChromaDB → RRF → FlashRank → top_k results.
        
        Returns list of dicts with: text, source_file, doc_type, score
        """
        if not self._chunks_meta:
            return []

        # 1. Vector search via ChromaDB
        vector_results = self._vector_search(query, n=50)

        # 2. Keyword search via BM25
        bm25_results = self._bm25_search(query, n=50)

        # 3. Reciprocal Rank Fusion
        fused = self._rrf_fusion(vector_results, bm25_results, k=60)

        # 4. FlashRank reranking on top-20
        top_candidates = fused[:20]
        if not top_candidates:
            return []

        reranked = self._rerank(query, top_candidates)

        return reranked[:top_k]

    def _vector_search(self, query: str, n: int = 50) -> list[dict]:
        """Search ChromaDB using the default embedding function."""
        try:
            count = self._collection.count()
            if count == 0:
                return []
            
            actual_n = min(n, count)
            results = self._collection.query(
                query_texts=[query],
                n_results=actual_n,
            )

            hits = []
            if results["ids"] and results["ids"][0]:
                for i, chunk_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    meta = self._chunks_meta.get(chunk_id, {})
                    hits.append({
                        "id": chunk_id,
                        "text": meta.get("text", results["documents"][0][i] if results.get("documents") else ""),
                        "source_file": meta.get("source_file", ""),
                        "doc_type": meta.get("doc_type", ""),
                        "score": 1 - distance,  # Convert distance to similarity
                    })
            return hits
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def _bm25_search(self, query: str, n: int = 50) -> list[dict]:
        """Search BM25S index for keyword matches."""
        if self._bm25 is None or not self._bm25_corpus:
            return []

        try:
            query_tokens = bm25s.tokenize([query], stemmer=None)
            results, scores = self._bm25.retrieve(query_tokens, k=min(n, len(self._bm25_corpus)))

            hits = []
            chunk_ids = list(self._chunks_meta.keys())
            for i in range(results.shape[1]):
                idx = results[0, i]
                score = float(scores[0, i])
                if idx < len(chunk_ids) and score > 0:
                    chunk_id = chunk_ids[idx]
                    meta = self._chunks_meta.get(chunk_id, {})
                    hits.append({
                        "id": chunk_id,
                        "text": meta.get("text", ""),
                        "source_file": meta.get("source_file", ""),
                        "doc_type": meta.get("doc_type", ""),
                        "score": score,
                    })
            return hits
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def _rrf_fusion(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        k: int = 60,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ) -> list[dict]:
        """Reciprocal Rank Fusion — merge vector and keyword results.
        
        RRF score = Σ weight / (k + rank)
        """
        scores: dict[str, float] = {}
        texts: dict[str, dict] = {}

        for rank, hit in enumerate(vector_results):
            cid = hit["id"]
            scores[cid] = scores.get(cid, 0) + vector_weight / (k + rank + 1)
            texts[cid] = hit

        for rank, hit in enumerate(bm25_results):
            cid = hit["id"]
            scores[cid] = scores.get(cid, 0) + bm25_weight / (k + rank + 1)
            if cid not in texts:
                texts[cid] = hit

        # Sort by fused score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results = []
        for cid in sorted_ids:
            item = texts[cid].copy()
            item["rrf_score"] = scores[cid]
            results.append(item)

        return results

    def _rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """Rerank candidates using FlashRank cross-encoder."""
        try:
            from flashrank import RerankRequest

            reranker = _get_reranker()
            passages = [{"id": c["id"], "text": c["text"], "meta": c} for c in candidates]

            rerank_request = RerankRequest(query=query, passages=passages)
            reranked = reranker.rerank(rerank_request)

            results = []
            for item in reranked:
                meta = item["meta"]
                meta["rerank_score"] = item["score"]
                results.append(meta)

            return results
        except Exception as e:
            logger.warning(f"FlashRank reranking failed, returning RRF order: {e}")
            return candidates

    # ── BM25 Management ───────────────────────────────────────────

    def _rebuild_bm25(self):
        """Rebuild the BM25 index from all chunk metadata."""
        if not self._chunks_meta:
            self._bm25 = None
            self._bm25_corpus = []
            return

        texts = [meta["text"] for meta in self._chunks_meta.values()]
        self._bm25_corpus = texts

        corpus_tokens = bm25s.tokenize(texts, stemmer=None)
        self._bm25 = bm25s.BM25()
        self._bm25.index(corpus_tokens)
        logger.info(f"Rebuilt BM25 index: {len(texts)} documents")

    def _load_bm25(self):
        """Try to load BM25 index from saved chunks."""
        # BM25 is rebuilt from chunks metadata, so just mark as needing rebuild
        pass

    # ── Persistence ───────────────────────────────────────────────

    def _save_chunks_meta(self):
        """Save chunk metadata to disk."""
        with open(self.chunks_file, "w", encoding="utf-8") as f:
            json.dump(self._chunks_meta, f, indent=2)

    def _load_chunks_meta(self):
        """Load chunk metadata from disk and rebuild BM25."""
        if os.path.exists(self.chunks_file):
            with open(self.chunks_file, "r", encoding="utf-8") as f:
                self._chunks_meta = json.load(f)
            if self._chunks_meta:
                self._rebuild_bm25()
                logger.info(f"Loaded {len(self._chunks_meta)} chunks for space '{self.space_id}'")

    @property
    def chunk_count(self) -> int:
        return len(self._chunks_meta)

    @property
    def file_list(self) -> list[str]:
        """Get unique source files indexed in this space."""
        return list(set(m.get("source_file", "") for m in self._chunks_meta.values()))


def make_chunk_id(source_file: str, index: int) -> str:
    """Generate a deterministic chunk ID from filename + index."""
    raw = f"{source_file}::{index}"
    return hashlib.md5(raw.encode()).hexdigest()
