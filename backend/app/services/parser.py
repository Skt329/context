"""Document parser — extracts raw text from PDF, DOCX, TXT, MD, CSV, PPTX files."""

import os
import csv
import io
import logging
import chardet

logger = logging.getLogger("contextai.parser")


def parse_file(file_path: str) -> str:
    """Extract text content from a file based on its extension.
    
    Returns the full raw text of the document.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    parsers = {
        ".pdf": _parse_pdf,
        ".docx": _parse_docx,
        ".pptx": _parse_pptx,
        ".csv": _parse_csv,
        ".txt": _parse_text,
        ".md": _parse_text,
        ".markdown": _parse_text,
        ".py": _parse_text,
        ".js": _parse_text,
        ".ts": _parse_text,
        ".json": _parse_text,
        ".yaml": _parse_text,
        ".yml": _parse_text,
        ".html": _parse_text,
        ".xml": _parse_text,
        ".log": _parse_text,
        ".ini": _parse_text,
        ".cfg": _parse_text,
        ".toml": _parse_text,
        ".rst": _parse_text,
    }

    parser = parsers.get(ext)
    if not parser:
        logger.warning(f"Unsupported file type: {ext} — trying as plain text")
        parser = _parse_text

    try:
        text = parser(file_path)
        logger.info(f"Parsed {os.path.basename(file_path)}: {len(text)} chars")
        return text
    except Exception as e:
        logger.error(f"Failed to parse {file_path}: {e}")
        return ""


def detect_document_type(filename: str, text: str) -> str:
    """Heuristic detection of document type for chunking strategy.
    
    Returns one of: 'resume', 'research', 'article', 'code', 'email', 'csv', 'general'
    """
    ext = os.path.splitext(filename)[1].lower()
    name_lower = filename.lower()

    # CSV is explicit
    if ext == ".csv":
        return "csv"

    # Code files
    if ext in (".py", ".js", ".ts", ".java", ".cpp", ".c", ".rs", ".go", ".rb", ".php"):
        return "code"

    # Resume heuristics
    resume_signals = ["resume", "cv", "curriculum vitae"]
    if any(s in name_lower for s in resume_signals):
        return "resume"

    text_lower = text[:3000].lower()
    resume_content_signals = ["experience", "education", "skills", "employment"]
    if sum(1 for s in resume_content_signals if s in text_lower) >= 3:
        return "resume"

    # Research heuristics
    research_signals = ["abstract", "references", "methodology", "conclusion", "et al."]
    if sum(1 for s in research_signals if s in text_lower) >= 3:
        return "research"

    # Email heuristics
    email_signals = ["from:", "to:", "subject:", "date:", "dear ", "regards"]
    if sum(1 for s in email_signals if s in text_lower) >= 3:
        return "email"

    return "general"


# ── Parsers ────────────────────────────────────────────────────────


def _parse_pdf(file_path: str) -> str:
    """Extract text from PDF using PyPDF2."""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages.append(f"--- Page {i + 1} ---\n{text}")
    return "\n\n".join(pages)


def _parse_docx(file_path: str) -> str:
    """Extract text from Word documents."""
    import docx

    doc = docx.Document(file_path)
    paragraphs = []
    for para in doc.paragraphs:
        if para.text.strip():
            # Preserve heading structure
            if para.style.name.startswith("Heading"):
                level = para.style.name.replace("Heading ", "")
                try:
                    prefix = "#" * int(level) + " "
                except ValueError:
                    prefix = "## "
                paragraphs.append(f"{prefix}{para.text}")
            else:
                paragraphs.append(para.text)

    # Also extract tables
    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(" | ".join(cells))
        if rows:
            paragraphs.append("\n".join(rows))

    return "\n\n".join(paragraphs)


def _parse_pptx(file_path: str) -> str:
    """Extract text from PowerPoint presentations."""
    from pptx import Presentation

    prs = Presentation(file_path)
    slides = []
    for i, slide in enumerate(prs.slides):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    if para.text.strip():
                        texts.append(para.text)
        if texts:
            slides.append(f"--- Slide {i + 1} ---\n" + "\n".join(texts))
    return "\n\n".join(slides)


def _parse_csv(file_path: str) -> str:
    """Extract text from CSV — include headers with each row batch."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return ""

    header = rows[0]
    lines = [", ".join(header)]  # First line is header
    for row in rows[1:]:
        lines.append(", ".join(row))

    return "\n".join(lines)


def _parse_text(file_path: str) -> str:
    """Read plain text files with encoding detection."""
    # Detect encoding
    with open(file_path, "rb") as f:
        raw = f.read()

    detected = chardet.detect(raw)
    encoding = detected.get("encoding", "utf-8") or "utf-8"

    try:
        return raw.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return raw.decode("utf-8", errors="replace")
