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

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    job_type TEXT NOT NULL,
    platform TEXT,
    creator_id TEXT,
    post_id TEXT,
    comment_id TEXT,
    status TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    next_retry_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME
);

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
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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


def init_database(database_path: Path | None = None) -> None:
    with db_session(database_path) as connection:
        connection.executescript(SCHEMA)
