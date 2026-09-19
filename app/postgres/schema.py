POSTGRES_JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    parent_job_id BIGINT REFERENCES jobs(id) ON DELETE SET NULL,
    idempotency_key TEXT UNIQUE,
    job_type TEXT NOT NULL,
    platform TEXT,
    creator_id TEXT,
    post_id TEXT,
    comment_id TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_runnable
ON jobs(status, next_retry_at, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_jobs_parent
ON jobs(parent_job_id, status);

CREATE TABLE IF NOT EXISTS job_dependencies (
    job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    depends_on_job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(job_id, depends_on_job_id)
);

CREATE INDEX IF NOT EXISTS idx_job_dependencies_target
ON job_dependencies(depends_on_job_id, job_id);

CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    current_job_id BIGINT REFERENCES jobs(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workers_heartbeat
ON workers(heartbeat_at);

CREATE TABLE IF NOT EXISTS rate_limits (
    key TEXT PRIMARY KEY,
    next_allowed_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


POSTGRES_CREATOR_POST_SCHEMA = """
CREATE TABLE IF NOT EXISTS creators (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    name TEXT,
    profile_url TEXT,
    avatar_url TEXT,
    bio TEXT,
    follower_count BIGINT,
    following_count BIGINT,
    discovered_post_count BIGINT,
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(platform, creator_id)
);

CREATE TABLE IF NOT EXISTS posts (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    content TEXT,
    post_type TEXT,
    published_at TIMESTAMPTZ,
    like_count BIGINT,
    favorite_count BIGINT,
    share_count BIGINT,
    reported_comment_count BIGINT,
    downloaded_comment_count BIGINT NOT NULL DEFAULT 0,
    comment_status TEXT,
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    platform_context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    detail_raw_json JSONB,
    discovery_fingerprint TEXT,
    detail_fingerprint TEXT,
    content_fingerprint TEXT,
    media_fingerprint TEXT,
    engagement_fingerprint TEXT,
    comments_fingerprint TEXT,
    last_discovered_at TIMESTAMPTZ,
    last_refreshed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(platform, post_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_creator
ON posts(platform, creator_id, id);
"""


POSTGRES_CONTENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS comments (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    comment_id TEXT NOT NULL,
    root_comment_id TEXT,
    parent_comment_id TEXT,
    user_id TEXT,
    user_name TEXT,
    user_avatar TEXT,
    content TEXT,
    like_count BIGINT,
    ip_location TEXT,
    published_at TIMESTAMPTZ,
    depth INTEGER NOT NULL DEFAULT 0,
    has_more_replies BOOLEAN NOT NULL DEFAULT FALSE,
    reply_count BIGINT NOT NULL DEFAULT 0,
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(platform, comment_id)
);

CREATE INDEX IF NOT EXISTS idx_comments_post_depth
ON comments(platform, post_id, depth, id);

CREATE TABLE IF NOT EXISTS media (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    post_id TEXT,
    comment_id TEXT,
    media_type TEXT NOT NULL,
    remote_url TEXT NOT NULL,
    local_path TEXT,
    storage_backend TEXT,
    storage_key TEXT,
    sha256 TEXT,
    width INTEGER,
    height INTEGER,
    duration DOUBLE PRECISION,
    download_status TEXT NOT NULL DEFAULT 'PENDING',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_media_unique_source
ON media(
    platform,
    COALESCE(post_id, ''),
    COALESCE(comment_id, ''),
    media_type,
    remote_url
);

CREATE INDEX IF NOT EXISTS idx_media_post_active
ON media(post_id, is_active, download_status);

CREATE TABLE IF NOT EXISTS ocr_results (
    id BIGSERIAL PRIMARY KEY,
    media_id BIGINT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    engine TEXT NOT NULL,
    engine_version TEXT,
    language TEXT,
    full_text TEXT NOT NULL,
    average_confidence DOUBLE PRECISION,
    blocks_json JSONB,
    status TEXT NOT NULL DEFAULT 'COMPLETE',
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(media_id, engine)
);

CREATE TABLE IF NOT EXISTS transcripts (
    id BIGSERIAL PRIMARY KEY,
    media_id BIGINT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    engine TEXT NOT NULL,
    engine_version TEXT,
    model TEXT,
    language TEXT,
    language_probability DOUBLE PRECISION,
    full_text TEXT NOT NULL,
    segments_json JSONB,
    status TEXT NOT NULL DEFAULT 'COMPLETE',
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(media_id, engine, model)
);

CREATE TABLE IF NOT EXISTS text_units (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    comment_id TEXT,
    media_id BIGINT REFERENCES media(id) ON DELETE CASCADE,
    unit_type TEXT NOT NULL,
    text TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    provenance TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_text_units_post
ON text_units(post_id, unit_type);

CREATE TABLE IF NOT EXISTS crawl_audits (
    id BIGSERIAL PRIMARY KEY,
    post_id TEXT NOT NULL,
    expected_comments BIGINT,
    actual_comments BIGINT,
    root_comments BIGINT,
    reply_comments BIGINT,
    failed_threads BIGINT NOT NULL DEFAULT 0,
    root_pagination_finished BOOLEAN NOT NULL DEFAULT FALSE,
    reply_threads_total BIGINT NOT NULL DEFAULT 0,
    reply_threads_finished BIGINT NOT NULL DEFAULT 0,
    pagination_finished BOOLEAN NOT NULL DEFAULT FALSE,
    completeness_ratio DOUBLE PRECISION,
    status TEXT,
    notes TEXT,
    audited_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    scope TEXT NOT NULL,
    object_id TEXT NOT NULL,
    cursor TEXT,
    finished BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(platform, scope, object_id)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_scope
ON checkpoints(platform, scope, object_id);
"""


POSTGRES_REFRESH_SCHEMA = """
CREATE TABLE IF NOT EXISTS change_events (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT,
    post_id TEXT,
    entity_type TEXT NOT NULL,
    change_type TEXT NOT NULL,
    old_fingerprint TEXT,
    new_fingerprint TEXT,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_change_events_creator
ON change_events(platform, creator_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_change_events_post
ON change_events(platform, post_id, detected_at DESC);

CREATE TABLE IF NOT EXISTS refresh_runs (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    new_posts BIGINT NOT NULL DEFAULT 0,
    changed_posts BIGINT NOT NULL DEFAULT 0,
    unchanged_posts BIGINT NOT NULL DEFAULT 0,
    pages_scanned BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS refresh_schedules (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL,
    max_pages INTEGER NOT NULL DEFAULT 3,
    max_recent_posts INTEGER NOT NULL DEFAULT 30,
    stop_after_unchanged_pages INTEGER NOT NULL DEFAULT 2,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at TIMESTAMPTZ NOT NULL,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(platform, creator_id)
);

CREATE INDEX IF NOT EXISTS idx_refresh_schedules_due
ON refresh_schedules(enabled, next_run_at);

CREATE TABLE IF NOT EXISTS raw_snapshots (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    cursor TEXT,
    payload_sha256 TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_snapshots_unique
ON raw_snapshots(
    platform,
    resource_type,
    object_id,
    COALESCE(cursor, ''),
    payload_sha256
);

CREATE INDEX IF NOT EXISTS idx_raw_snapshots_object
ON raw_snapshots(platform, resource_type, object_id, captured_at);
"""
