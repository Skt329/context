"""Tests for the SQLite database layer and data migration."""

import os
import json
import sqlite3
import pytest

import app.db as db_module


class TestDatabaseInit:
    """Tests for database initialization."""

    def test_init_creates_tables(self, temp_db):
        """init_db should create all required tables."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert "conversations" in tables
        assert "spaces" in tables
        assert "settings" in tables
        assert "memory" in tables

    def test_init_is_idempotent(self, temp_db):
        """Running init_db twice should not error or duplicate tables."""
        db_module.init_db()  # Second call
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        assert tables.count("conversations") == 1

    def test_wal_mode_enabled(self, temp_db):
        """Database should use WAL journal mode."""
        conn = db_module.get_db()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"


class TestConversationsCRUD:
    """Tests for conversation database operations."""

    def test_insert_and_read(self, temp_db):
        """Should insert and retrieve a conversation."""
        conn = db_module.get_db()
        conn.execute(
            "INSERT INTO conversations (id, space_id, title, messages, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("c1", "s1", "Test", "[]", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM conversations WHERE id = 'c1'").fetchone()
        conn.close()

        assert row["id"] == "c1"
        assert row["title"] == "Test"
        assert row["space_id"] == "s1"

    def test_list_by_space(self, populated_db):
        """Should filter conversations by space_id."""
        conn = db_module.get_db()
        rows = conn.execute(
            "SELECT * FROM conversations WHERE space_id = ?", ("test-space-1",)
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]["title"] == "Test Chat"

    def test_update_title(self, populated_db):
        """Should update conversation title."""
        conn = db_module.get_db()
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            ("Updated Title", "test-convo-1"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT title FROM conversations WHERE id = 'test-convo-1'"
        ).fetchone()
        conn.close()

        assert row["title"] == "Updated Title"

    def test_delete(self, populated_db):
        """Should delete a conversation."""
        conn = db_module.get_db()
        conn.execute("DELETE FROM conversations WHERE id = 'test-convo-1'")
        conn.commit()

        row = conn.execute(
            "SELECT * FROM conversations WHERE id = 'test-convo-1'"
        ).fetchone()
        conn.close()

        assert row is None

    def test_messages_json_roundtrip(self, populated_db):
        """Messages should survive JSON serialization roundtrip."""
        conn = db_module.get_db()
        row = conn.execute(
            "SELECT messages FROM conversations WHERE id = 'test-convo-1'"
        ).fetchone()
        conn.close()

        messages = json.loads(row["messages"])
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "Hi there!"


class TestMemoryCRUD:
    """Tests for memory database operations."""

    def test_global_memory_read(self, populated_db):
        """Should read global memory."""
        conn = db_module.get_db()
        row = conn.execute(
            "SELECT content FROM memory WHERE scope = 'global' AND space_id = ''"
        ).fetchone()
        conn.close()

        assert "User prefers Python" in row["content"]

    def test_space_memory_read(self, populated_db):
        """Should read space-specific memory."""
        conn = db_module.get_db()
        row = conn.execute(
            "SELECT content FROM memory WHERE scope = 'space' AND space_id = ?",
            ("test-space-1",),
        ).fetchone()
        conn.close()

        assert "ML project" in row["content"]

    def test_memory_upsert(self, temp_db):
        """Should upsert memory (insert then update)."""
        conn = db_module.get_db()

        # Insert
        conn.execute(
            "INSERT INTO memory (scope, space_id, content, updated_at) VALUES (?, ?, ?, ?)",
            ("global", "", "fact 1", "2024-01-01"),
        )
        conn.commit()

        # Update via conflict
        conn.execute(
            """INSERT INTO memory (scope, space_id, content, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(scope, space_id) DO UPDATE SET content = ?, updated_at = ?""",
            ("global", "", "fact 2", "2024-01-02", "fact 2", "2024-01-02"),
        )
        conn.commit()

        row = conn.execute("SELECT content FROM memory WHERE scope = 'global'").fetchone()
        conn.close()

        assert row["content"] == "fact 2"


class TestSettingsCRUD:
    """Tests for settings database operations."""

    def test_insert_and_read_setting(self, temp_db):
        """Should store and retrieve a JSON setting."""
        conn = db_module.get_db()
        providers = {"openai": {"enabled": True, "model": "gpt-4"}}
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("providers", json.dumps(providers)),
        )
        conn.commit()

        row = conn.execute("SELECT value FROM settings WHERE key = 'providers'").fetchone()
        conn.close()

        result = json.loads(row["value"])
        assert result["openai"]["model"] == "gpt-4"
