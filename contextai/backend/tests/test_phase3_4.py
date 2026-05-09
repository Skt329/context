"""Phase 3 + 4 tests — FTS search, export, task queue, tools, error log, middleware."""

import json
import sqlite3
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock


# ── FTS5 Search Tests ─────────────────────────────────────────

class TestFTSSearch:
    """Test the full-text search infrastructure."""

    def test_fts_table_created(self, temp_db):
        """Verify FTS5 virtual table exists after init."""
        conn = sqlite3.connect(temp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations_fts'"
        ).fetchone()
        conn.close()
        assert tables is not None, "conversations_fts table should exist"

    def test_fts_trigger_on_insert(self, temp_db):
        """Verify FTS syncs on conversation insert."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO conversations (id, space_id, title, messages, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("fts-1", "default", "Python tutorial", json.dumps([{"role": "user", "content": "Teach me Python"}]), "2024-01-01", "2024-01-01"),
        )
        conn.commit()

        # Search using FTS match — join back to conversations for readable columns
        results = conn.execute(
            """SELECT c.title FROM conversations c
               JOIN conversations_fts fts ON c.rowid = fts.rowid
               WHERE conversations_fts MATCH ?""",
            ("Python",),
        ).fetchall()
        conn.close()
        assert len(results) >= 1
        assert results[0]["title"] == "Python tutorial"

    def test_fts_trigger_on_delete(self, temp_db):
        """Verify FTS removes data on conversation delete."""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO conversations (id, space_id, title, messages, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("fts-del", "default", "Delete me", json.dumps([]), "2024-01-01", "2024-01-01"),
        )
        conn.commit()
        conn.execute("DELETE FROM conversations WHERE id = 'fts-del'")
        conn.commit()

        results = conn.execute(
            "SELECT * FROM conversations_fts WHERE conversations_fts MATCH ?",
            ("Delete",),
        ).fetchall()
        conn.close()
        assert len(results) == 0


# ── Error Log Tests ───────────────────────────────────────────

class TestErrorLog:
    """Test the error_log table."""

    def test_error_log_table_exists(self, temp_db):
        """Verify error_log table is created by init_db."""
        conn = sqlite3.connect(temp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='error_log'"
        ).fetchone()
        conn.close()
        assert tables is not None

    def test_insert_error_log(self, temp_db):
        """Verify errors can be inserted and queried."""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO error_log (request_id, method, path, error_type, error_message, traceback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("abc123", "POST", "/api/chat/stream", "ValueError", "test error", "traceback...", "2024-01-01T00:00:00"),
        )
        conn.commit()

        rows = conn.execute("SELECT * FROM error_log ORDER BY created_at DESC").fetchall()
        conn.close()
        assert len(rows) == 1


# ── Task Queue Tests ──────────────────────────────────────────

class TestTaskQueue:
    """Test the background task queue."""

    @pytest.mark.asyncio
    async def test_enqueue_and_complete(self):
        """Task should go from pending → done."""
        from app.tasks import TaskQueue

        q = TaskQueue()
        await q.start()

        async def mock_task():
            await asyncio.sleep(0.01)
            return {"indexed": 5}

        task_id = await q.enqueue("t1", mock_task())

        # Wait for completion
        await asyncio.sleep(0.1)

        status = q.get_status("t1")
        assert status is not None
        assert status["status"] == "done"
        assert status["result"]["indexed"] == 5

        await q.stop()

    @pytest.mark.asyncio
    async def test_enqueue_error(self):
        """Failed tasks should have error status."""
        from app.tasks import TaskQueue

        q = TaskQueue()
        await q.start()

        async def failing_task():
            raise ValueError("boom")

        await q.enqueue("t2", failing_task())
        await asyncio.sleep(0.1)

        status = q.get_status("t2")
        assert status["status"] == "error"
        assert "boom" in status["error"]

        await q.stop()

    @pytest.mark.asyncio
    async def test_list_tasks(self):
        """List should return recent tasks."""
        from app.tasks import TaskQueue

        q = TaskQueue()
        await q.start()

        async def noop():
            pass

        await q.enqueue("t3", noop())
        await asyncio.sleep(0.05)

        tasks = q.list_tasks()
        assert len(tasks) >= 1
        assert any(t["task_id"] == "t3" for t in tasks)

        await q.stop()


# ── Tool Execution Tests ──────────────────────────────────────

class TestToolExecution:
    """Test the built-in tool engine."""

    @pytest.mark.asyncio
    async def test_calculate(self):
        from app.services.tools import execute_tool
        result = await execute_tool("calculate", {"expression": "2 + 3 * 4"})
        assert "14" in result

    @pytest.mark.asyncio
    async def test_calculate_sqrt(self):
        from app.services.tools import execute_tool
        result = await execute_tool("calculate", {"expression": "sqrt(144)"})
        assert "12" in result

    @pytest.mark.asyncio
    async def test_calculate_error(self):
        from app.services.tools import execute_tool
        result = await execute_tool("calculate", {"expression": "import os"})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_get_current_time(self):
        from app.services.tools import execute_tool
        result = await execute_tool("get_current_time", {})
        assert "UTC" in result
        assert "Local" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        from app.services.tools import execute_tool
        result = await execute_tool("nonexistent_tool", {})
        assert "Unknown" in result

    def test_tool_definitions_format(self):
        from app.services.tools import get_tool_definitions
        defs = get_tool_definitions()
        assert len(defs) >= 3
        for d in defs:
            assert d["type"] == "function"
            assert "function" in d
            assert "name" in d["function"]
            assert "description" in d["function"]
            assert "parameters" in d["function"]

    @pytest.mark.asyncio
    async def test_memory_summary_empty(self, temp_db):
        from app.services.tools import execute_tool
        result = await execute_tool("get_memory_summary", {"space_id": "nonexistent"})
        # Should not crash, may return "No memory found"
        assert isinstance(result, str)


# ── Middleware Tests ──────────────────────────────────────────

class TestCorrelationMiddleware:
    """Test request correlation ID assignment."""

    def test_middleware_imports(self):
        """Ensure middleware module loads without errors."""
        from app.middleware import CorrelationMiddleware, ErrorReportingMiddleware
        assert CorrelationMiddleware is not None
        assert ErrorReportingMiddleware is not None
