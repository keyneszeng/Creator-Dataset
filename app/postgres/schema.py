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
