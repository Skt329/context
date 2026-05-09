"""SQLite database layer with WAL mode for ACID-compliant storage.

Replaces the legacy JSON-file-per-conversation approach with a single
SQLite database at ~/.contextai/contextai.db.  Migration from the old
filesystem layout happens automatically on first startup.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger("contextai.db")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".contextai")
DB_PATH = os.path.join(DATA_DIR, "contextai.db")

# ── Schema ────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id            TEXT PRIMARY KEY,
    space_id      TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT 'New Chat',
    messages      TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_space ON conversations(space_id);
CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC);

CREATE TABLE IF NOT EXISTS spaces (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    icon          TEXT NOT NULL DEFAULT '📁',
    description   TEXT NOT NULL DEFAULT '',
    file_count    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key           TEXT PRIMARY KEY,
    value         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scope         TEXT NOT NULL,
    space_id      TEXT NOT NULL DEFAULT '',
    content       TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL,
    UNIQUE(scope, space_id)
);

-- Full-text search index for conversations (title + message content)
CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
    title,
    messages_text,
    content=conversations,
    content_rowid=rowid
);

-- Keep FTS in sync with conversations table
CREATE TRIGGER IF NOT EXISTS conversations_fts_insert AFTER INSERT ON conversations BEGIN
    INSERT INTO conversations_fts(rowid, title, messages_text)
    VALUES (new.rowid, new.title, new.messages);
END;

CREATE TRIGGER IF NOT EXISTS conversations_fts_update AFTER UPDATE ON conversations BEGIN
    INSERT INTO conversations_fts(conversations_fts, rowid, title, messages_text)
    VALUES ('delete', old.rowid, old.title, old.messages);
    INSERT INTO conversations_fts(rowid, title, messages_text)
    VALUES (new.rowid, new.title, new.messages);
END;

CREATE TRIGGER IF NOT EXISTS conversations_fts_delete AFTER DELETE ON conversations BEGIN
    INSERT INTO conversations_fts(conversations_fts, rowid, title, messages_text)
    VALUES ('delete', old.rowid, old.title, old.messages);
END;

-- Error log for unhandled exceptions (Task 39)
CREATE TABLE IF NOT EXISTS error_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id    TEXT NOT NULL DEFAULT '',
    method        TEXT NOT NULL DEFAULT '',
    path          TEXT NOT NULL DEFAULT '',
    error_type    TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    traceback     TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_error_log_created ON error_log(created_at DESC);
"""


# ── Connection ────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Get a database connection with WAL mode and foreign keys enabled."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    finally:
        conn.close()


# ── Migration from legacy JSON/MD files ───────────────────────────

def _needs_migration() -> bool:
    """Check if there's legacy data to migrate."""
    legacy_convos = os.path.join(DATA_DIR, "conversations")
    legacy_settings = os.path.join(DATA_DIR, "settings.json")
    return os.path.isdir(legacy_convos) or os.path.isfile(legacy_settings)


def migrate_from_legacy():
    """One-time migration: read all legacy JSON/MD files into SQLite.

    This is idempotent — it skips records that already exist in the DB.
    After migration, legacy directories are renamed to *.bak.
    """
    if not _needs_migration():
        return

    conn = get_db()
    migrated = {"conversations": 0, "spaces": 0, "settings": 0, "memory": 0}

    try:
        # ── 1. Migrate conversations ──────────────────────────────
        convos_dir = os.path.join(DATA_DIR, "conversations")
        if os.path.isdir(convos_dir):
            for entry in os.scandir(convos_dir):
                if entry.name.endswith(".json") and entry.is_file():
                    try:
                        with open(entry.path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        conn.execute(
                            """INSERT OR IGNORE INTO conversations 
                               (id, space_id, title, messages, created_at, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                data["id"],
                                data.get("spaceId", "default"),
                                data.get("title", "New Chat"),
                                json.dumps(data.get("messages", []), ensure_ascii=False),
                                data.get("createdAt", datetime.utcnow().isoformat()),
                                data.get("updatedAt", datetime.utcnow().isoformat()),
                            ),
                        )
                        migrated["conversations"] += 1
                    except Exception as e:
                        logger.warning(f"Skipping corrupt conversation {entry.name}: {e}")

        # ── 2. Migrate spaces ─────────────────────────────────────
        spaces_dir = os.path.join(DATA_DIR, "spaces")
        if os.path.isdir(spaces_dir):
            for entry in os.scandir(spaces_dir):
                if entry.is_dir():
                    meta_path = os.path.join(entry.path, "meta.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r") as f:
                                meta = json.load(f)
                            conn.execute(
                                """INSERT OR IGNORE INTO spaces
                                   (id, name, icon, description, file_count, created_at, updated_at)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    meta["id"],
                                    meta.get("name", "Untitled"),
                                    meta.get("icon", "📁"),
                                    meta.get("description", ""),
                                    meta.get("file_count", 0),
                                    meta.get("created_at", datetime.utcnow().isoformat()),
                                    meta.get("updated_at", datetime.utcnow().isoformat()),
                                ),
                            )
                            migrated["spaces"] += 1
                        except Exception as e:
                            logger.warning(f"Skipping space {entry.name}: {e}")

                    # Migrate space memory
                    mem_path = os.path.join(entry.path, "space_memory.md")
                    if os.path.exists(mem_path):
                        try:
                            content = open(mem_path, "r", encoding="utf-8").read()
                            if content.strip():
                                conn.execute(
                                    """INSERT OR IGNORE INTO memory 
                                       (scope, space_id, content, updated_at) 
                                       VALUES (?, ?, ?, ?)""",
                                    ("space", entry.name, content, datetime.utcnow().isoformat()),
                                )
                                migrated["memory"] += 1
                        except Exception:
                            pass

                    # Migrate user profile
                    profile_path = os.path.join(entry.path, "user_profile.md")
                    if os.path.exists(profile_path):
                        try:
                            content = open(profile_path, "r", encoding="utf-8").read()
                            if content.strip():
                                conn.execute(
                                    """INSERT OR IGNORE INTO memory 
                                       (scope, space_id, content, updated_at) 
                                       VALUES (?, ?, ?, ?)""",
                                    ("profile", entry.name, content, datetime.utcnow().isoformat()),
                                )
                                migrated["memory"] += 1
                        except Exception:
                            pass

        # ── 3. Migrate global memory ──────────────────────────────
        global_mem = os.path.join(DATA_DIR, "global_memory.md")
        if os.path.exists(global_mem):
            try:
                content = open(global_mem, "r", encoding="utf-8").read()
                if content.strip():
                    conn.execute(
                        """INSERT OR IGNORE INTO memory 
                           (scope, space_id, content, updated_at) 
                           VALUES (?, ?, ?, ?)""",
                        ("global", "", content, datetime.utcnow().isoformat()),
                    )
                    migrated["memory"] += 1
            except Exception:
                pass

        # ── 4. Migrate settings ───────────────────────────────────
        settings_path = os.path.join(DATA_DIR, "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                for key, value in settings.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                        (key, json.dumps(value, ensure_ascii=False)),
                    )
                migrated["settings"] += 1
            except Exception as e:
                logger.warning(f"Settings migration failed: {e}")

        conn.commit()

        # ── 5. Rename legacy directories ──────────────────────────
        for name in ["conversations", "settings.json", "global_memory.md"]:
            path = os.path.join(DATA_DIR, name)
            bak = path + ".bak"
            if os.path.exists(path) and not os.path.exists(bak):
                try:
                    os.rename(path, bak)
                except Exception:
                    pass  # Non-critical — old files just stay

        logger.info(
            f"Migration complete: {migrated['conversations']} conversations, "
            f"{migrated['spaces']} spaces, {migrated['memory']} memory entries, "
            f"{migrated['settings']} settings"
        )

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()
