"""Document-type-aware chunking engine.

Implements Anthropic's Contextual Retrieval approach:
1. Split documents into chunks using type-specific strategies
2. Optionally contextualize each chunk with a cheap LLM call
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("contextai.chunking")


@dataclass
class Chunk:
    """A single chunk of document text with metadata."""
    text: str
    index: int
    source_file: str
    doc_type: str
    metadata: dict = field(default_factory=dict)
    contextualized_text: str | None = None  # Set after contextualization

    @property
    def final_text(self) -> str:
        """Return contextualized text if available, else raw text."""
        return self.contextualized_text or self.text


def chunk_document(text: str, doc_type: str, source_file: str) -> list[Chunk]:
    """Split a document into chunks using the appropriate strategy.
    
    Args:
        text: Full document text
        doc_type: One of 'resume', 'research', 'article', 'code', 'email', 'csv', 'general'
        source_file: Original filename for metadata
    
    Returns:
        List of Chunk objects
    """
    strategies = {
        "resume": _chunk_by_sections,
        "research": _chunk_by_paragraphs_large,
        "code": _chunk_by_functions,
        "email": _chunk_by_messages,
        "csv": _chunk_csv_rows,
        "general": _chunk_by_paragraphs,
    }

    strategy = strategies.get(doc_type, _chunk_by_paragraphs)
    raw_chunks = strategy(text)

    # Filter empty chunks and create Chunk objects
    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        cleaned = chunk_text.strip()
        if len(cleaned) < 20:  # Skip tiny fragments
            continue
        chunks.append(Chunk(
            text=cleaned,
            index=i,
            source_file=source_file,
            doc_type=doc_type,
        ))

    logger.info(f"Chunked '{source_file}' ({doc_type}): {len(chunks)} chunks from {len(text)} chars")
    return chunks


# ── Chunking Strategies ───────────────────────────────────────────


def _chunk_by_sections(text: str) -> list[str]:
    """Resume/CV: split by markdown headers or common section patterns.
    
    Each section becomes one chunk (variable size).
    """
    # Try markdown headers first
    sections = re.split(r'\n(?=#{1,3}\s)', text)
    if len(sections) > 2:
        return sections

    # Try common resume section headers
    section_patterns = [
        r'\n(?=(?:EXPERIENCE|EDUCATION|SKILLS|PROJECTS|CERTIFICATIONS|'
        r'WORK EXPERIENCE|PROFESSIONAL EXPERIENCE|SUMMARY|OBJECTIVE|'
        r'TECHNICAL SKILLS|AWARDS|PUBLICATIONS|LANGUAGES|INTERESTS|'
        r'Experience|Education|Skills|Projects|Summary)\s*\n)',
    ]
    for pattern in section_patterns:
        sections = re.split(pattern, text)
        if len(sections) > 2:
            return sections

    # Fallback to paragraph-based
    return _chunk_by_paragraphs(text)


def _chunk_by_paragraphs_large(text: str, target_size: int = 1500, overlap: int = 200) -> list[str]:
    """Research papers: larger chunks (~512 tokens ≈ 1500 chars) with overlap."""
    return _sliding_window_chunk(text, target_size, overlap)


def _chunk_by_paragraphs(text: str, target_size: int = 800, overlap: int = 100) -> list[str]:
    """General text: medium chunks (~256 tokens ≈ 800 chars) with small overlap."""
    return _sliding_window_chunk(text, target_size, overlap)


def _chunk_by_functions(text: str) -> list[str]:
    """Code files: split by function/class definitions.
    
    Each function/class becomes one chunk, including docstring.
    """
    # Python function/class pattern
    py_pattern = r'\n(?=(?:def |class |async def ))'
    parts = re.split(py_pattern, text)
    if len(parts) > 2:
        return parts

    # JavaScript/TypeScript patterns
    js_pattern = r'\n(?=(?:function |export (?:default )?(?:function|class|const)|class ))'
    parts = re.split(js_pattern, text)
    if len(parts) > 2:
        return parts

    # Fallback to paragraph-based for other languages
    return _chunk_by_paragraphs(text, target_size=1200, overlap=100)


def _chunk_by_messages(text: str) -> list[str]:
    """Email threads: split per message boundary."""
    # Common email separators
    patterns = [
        r'\n(?=From:)',
        r'\n(?=On .+ wrote:)',
        r'\n(?=[-]{3,})',
        r'\n(?=_{3,})',
    ]
    for pattern in patterns:
        parts = re.split(pattern, text)
        if len(parts) > 1:
            return parts

    # Single email — chunk as paragraphs
    return _chunk_by_paragraphs(text)


def _chunk_csv_rows(text: str, batch_size: int = 50) -> list[str]:
    """CSV: batch rows with header repeated.
    
    Each chunk contains the header row + 50 data rows.
    """
    lines = text.strip().split("\n")
    if len(lines) <= 1:
        return [text]

    header = lines[0]
    data_lines = lines[1:]
    chunks = []

    for i in range(0, len(data_lines), batch_size):
        batch = data_lines[i:i + batch_size]
        chunk = header + "\n" + "\n".join(batch)
        chunks.append(chunk)

    return chunks


# ── Utilities ─────────────────────────────────────────────────────


def _sliding_window_chunk(text: str, target_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks at paragraph boundaries.
    
    Tries to break at paragraph boundaries (double newline),
    falling back to sentence boundaries, then hard character splits.
    """
    # Split into paragraphs first
    paragraphs = re.split(r'\n\s*\n', text)
    
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph exceeds target, save current and start new
        if len(current_chunk) + len(para) + 2 > target_size and current_chunk:
            chunks.append(current_chunk)
            # Start new chunk with overlap from end of previous
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + "\n\n" + para
            else:
                current_chunk = para
        else:
            current_chunk = (current_chunk + "\n\n" + para).strip()

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk)

    # If no paragraph breaks found and text is large, do hard splits
    if len(chunks) <= 1 and len(text) > target_size * 2:
        return _hard_chunk(text, target_size, overlap)

    return chunks


def _hard_chunk(text: str, target_size: int, overlap: int) -> list[str]:
    """Last resort: split at sentence boundaries within fixed windows."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > target_size and current:
            chunks.append(current)
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + " " + sentence
            else:
                current = sentence
        else:
            current = (current + " " + sentence).strip()

    if current.strip():
        chunks.append(current)

    return chunks
