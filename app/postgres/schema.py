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
