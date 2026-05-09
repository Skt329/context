"""Shared test fixtures for ContextAI backend tests."""

import os
import sys
import sqlite3
import pytest
import tempfile

# Add backend to sys.path so app imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database for testing.
    
    Patches app.db.DB_PATH so all database operations use the temp DB.
    """
    db_path = str(tmp_path / "test_contextai.db")
    
    import app.db as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_path
    db_module.init_db()
    
    yield db_path
    
    db_module.DB_PATH = original_path


@pytest.fixture
def populated_db(temp_db):
    """A temp DB pre-populated with sample data for testing."""
    import app.db as db_module
    
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    
    # Insert sample spaces
    conn.execute(
        "INSERT INTO spaces (id, name, icon, description, file_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("test-space-1", "Test Space", "🧪", "For testing", 0, "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
    )
    
    # Insert sample conversations
    import json
    messages = json.dumps([
        {"id": "m1", "role": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00"},
        {"id": "m2", "role": "assistant", "content": "Hi there!", "timestamp": "2024-01-01T00:00:01"},
    ])
    conn.execute(
        "INSERT INTO conversations (id, space_id, title, messages, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("test-convo-1", "test-space-1", "Test Chat", messages, "2024-01-01T00:00:00", "2024-01-01T00:00:01"),
    )
    
    # Insert sample memory
    conn.execute(
        "INSERT INTO memory (scope, space_id, content, updated_at) VALUES (?, ?, ?, ?)",
        ("global", "", "# Memory\n- User prefers Python\n", "2024-01-01T00:00:00"),
    )
    conn.execute(
        "INSERT INTO memory (scope, space_id, content, updated_at) VALUES (?, ?, ?, ?)",
        ("space", "test-space-1", "# Space Memory\n- Working on ML project\n", "2024-01-01T00:00:00"),
    )
    
    conn.commit()
    conn.close()
    
    yield temp_db


@pytest.fixture
def sample_documents():
    """Sample document texts for RAG/chunking tests."""
    return {
        "resume.txt": (
            "# Experience\n"
            "Software Engineer at Google (2019-2024)\n"
            "- Built large-scale distributed systems\n"
            "- Led team of 5 engineers\n\n"
            "# Education\n"
            "Stanford University, MS Computer Science (2019)\n"
            "MIT, BS Computer Science (2017)\n"
        ),
        "research.txt": (
            "Abstract: This paper presents a novel approach to retrieval-augmented generation. "
            "We propose a hybrid method combining dense and sparse retrieval with learned reranking. "
            "Our approach achieves state-of-the-art results on multiple benchmarks.\n\n"
            "Introduction: Large language models have shown remarkable capabilities..."
        ),
        "code.py": (
            "def fibonacci(n: int) -> int:\n"
            '    """Calculate the nth Fibonacci number."""\n'
            "    if n <= 1:\n"
            "        return n\n"
            "    return fibonacci(n - 1) + fibonacci(n - 2)\n\n\n"
            "def factorial(n: int) -> int:\n"
            '    """Calculate n factorial."""\n'
            "    if n <= 1:\n"
            "        return 1\n"
            "    return n * factorial(n - 1)\n"
        ),
    }
