import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.settings import get_settings

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS creators (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    name TEXT,
    profile_url TEXT,
    avatar_url TEXT,
    bio TEXT,
    follower_count INTEGER,
    following_count INTEGER,
    discovered_post_count INTEGER,
    raw_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, creator_id)
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    content TEXT,
    post_type TEXT,
    published_at DATETIME,
    like_count INTEGER,
    favorite_count INTEGER,
    share_count INTEGER,
    reported_comment_count INTEGER,
    downloaded_comment_count INTEGER DEFAULT 0,
    comment_status TEXT,
    raw_json TEXT,
    platform_context_json TEXT,
    detail_raw_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, post_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    comment_id TEXT NOT NULL,
    root_comment_id TEXT,
    parent_comment_id TEXT,
    user_id TEXT,
    user_name TEXT,
    user_avatar TEXT,
    content TEXT,
    like_count INTEGER,
    ip_location TEXT,
    published_at DATETIME,
    depth INTEGER DEFAULT 0,
    has_more_replies BOOLEAN,
    reply_count INTEGER,
    raw_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, comment_id)
);

CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    post_id TEXT,
    comment_id TEXT,
    media_type TEXT NOT NULL,
    remote_url TEXT NOT NULL,
    local_path TEXT,
    sha256 TEXT,
    width INTEGER,
    height INTEGER,
    duration REAL,
    download_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_media_unique_source
ON media(
    platform,
    IFNULL(post_id, ''),
    IFNULL(comment_id, ''),
    media_type,
    remote_url
);

CREATE TABLE IF NOT EXISTS ocr_results (
    id INTEGER PRIMARY KEY,
    media_id INTEGER NOT NULL,
    engine TEXT NOT NULL,
    engine_version TEXT,
    language TEXT,
    full_text TEXT NOT NULL,
    average_confidence REAL,
    blocks_json TEXT,
    status TEXT NOT NULL DEFAULT 'COMPLETE',
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(media_id, engine),
    FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY,
    media_id INTEGER NOT NULL,
    engine TEXT NOT NULL,
    engine_version TEXT,
    model TEXT,
    language TEXT,
    language_probability REAL,
    full_text TEXT NOT NULL,
    segments_json TEXT,
    status TEXT NOT NULL DEFAULT 'COMPLETE',
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(media_id, engine, model),
    FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS text_units (
    id INTEGER PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    comment_id TEXT,
    media_id INTEGER,
    unit_type TEXT NOT NULL,
    text TEXT NOT NULL,
    confidence REAL,
    provenance TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_text_units_post
ON text_units(post_id, unit_type);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    parent_job_id INTEGER,
    idempotency_key TEXT UNIQUE,
    job_type TEXT NOT NULL,
    platform TEXT,
    creator_id TEXT,
    post_id TEXT,
    comment_id TEXT,
    payload_json TEXT,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    next_retry_at DATETIME,
    lease_owner TEXT,
    lease_expires_at DATETIME,
    heartbeat_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    FOREIGN KEY(parent_job_id) REFERENCES jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_runnable
ON jobs(status, next_retry_at, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_jobs_parent
ON jobs(parent_job_id, status);

CREATE TABLE IF NOT EXISTS crawl_audits (
    id INTEGER PRIMARY KEY,
    post_id TEXT NOT NULL,
    expected_comments INTEGER,
    actual_comments INTEGER,
    root_comments INTEGER,
    reply_comments INTEGER,
    failed_threads INTEGER DEFAULT 0,
    root_pagination_finished BOOLEAN DEFAULT 0,
    reply_threads_total INTEGER DEFAULT 0,
    reply_threads_finished INTEGER DEFAULT 0,
    pagination_finished BOOLEAN DEFAULT 0,
    completeness_ratio REAL,
    status TEXT,
    notes TEXT,
    audited_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rate_limits (
    key TEXT PRIMARY KEY,
    next_allowed_at REAL NOT NULL DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    scope TEXT NOT NULL,
    object_id TEXT NOT NULL,
    cursor TEXT,
    finished BOOLEAN NOT NULL DEFAULT 0,
    metadata_json TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, scope, object_id)
);
"""


def connect(database_path: Path | None = None) -> sqlite3.Connection:
    path = database_path or get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


@contextmanager
def db_session(database_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    connection = connect(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _ensure_column(
    connection: sqlite3.Connection,
    *,
    table: str,
    column: str,
    definition: str,
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row["name"] for row in rows}
    if column not in existing:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_database(database_path: Path | None = None) -> None:
    with db_session(database_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)
        _ensure_column(
            connection,
            table="posts",
            column="platform_context_json",
            definition="TEXT",
        )
        _ensure_column(
            connection,
            table="posts",
            column="detail_raw_json",
            definition="TEXT",
        )
        for column, definition in (
            ("parent_job_id", "INTEGER"),
            ("idempotency_key", "TEXT"),
            ("payload_json", "TEXT"),
            ("priority", "INTEGER NOT NULL DEFAULT 100"),
            ("attempt", "INTEGER NOT NULL DEFAULT 0"),
            ("max_attempts", "INTEGER NOT NULL DEFAULT 5"),
            ("lease_owner", "TEXT"),
            ("lease_expires_at", "DATETIME"),
            ("heartbeat_at", "DATETIME"),
        ):
            _ensure_column(
                connection,
                table="jobs",
                column=column,
                definition=definition,
            )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency "
            "ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_runnable "
            "ON jobs(status, next_retry_at, priority, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_parent "
            "ON jobs(parent_job_id, status)"
        )
