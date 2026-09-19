from typing import Any

from app.core.checkpoints import CheckpointRepository
from app.core.repositories import (
    AuditRepository,
    ChangeEventRepository,
    CommentRepository,
    CreatorRepository,
    ExportRepository,
    JobRepository,
    MediaRepository,
    OcrRepository,
    PostRepository,
    RawSnapshotRepository,
    RefreshRunRepository,
    RefreshScheduleRepository,
    TextUnitRepository,
    TranscriptRepository,
    WorkerRepository,
)
from app.core.settings import Settings, get_settings


def _settings(settings: Settings | None = None) -> Settings:
    return settings or get_settings()


def _database_url(settings: Settings) -> str:
    if not settings.database_url:
        raise ValueError(
            "CREATOR_DATASET_DATABASE_URL is required for PostgreSQL."
        )
    return settings.database_url


def create_creator_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return CreatorRepository()
    from app.postgres.creator_posts import PostgresCreatorRepository
    return PostgresCreatorRepository(_database_url(settings))


def create_post_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return PostRepository()
    from app.postgres.creator_posts import PostgresPostRepository
    return PostgresPostRepository(_database_url(settings))


def create_comment_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return CommentRepository()
    from app.postgres.content import PostgresCommentRepository
    return PostgresCommentRepository(_database_url(settings))


def create_checkpoint_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return CheckpointRepository()
    from app.postgres.content import PostgresCheckpointRepository
    return PostgresCheckpointRepository(_database_url(settings))


def create_audit_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return AuditRepository()
    from app.postgres.content import PostgresAuditRepository
    return PostgresAuditRepository(_database_url(settings))


def create_media_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return MediaRepository()
    from app.postgres.content import PostgresMediaRepository
    return PostgresMediaRepository(_database_url(settings))


def create_ocr_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return OcrRepository()
    from app.postgres.content import PostgresOcrRepository
    return PostgresOcrRepository(_database_url(settings))


def create_transcript_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return TranscriptRepository()
    from app.postgres.content import PostgresTranscriptRepository
    return PostgresTranscriptRepository(_database_url(settings))


def create_export_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return ExportRepository()
    from app.postgres.content import PostgresExportRepository
    return PostgresExportRepository(_database_url(settings))


def create_text_unit_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return TextUnitRepository()
    from app.postgres.content import PostgresTextUnitRepository
    return PostgresTextUnitRepository(_database_url(settings))


def create_job_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return JobRepository()
    from app.postgres.jobs import PostgresJobRepository
    return PostgresJobRepository(_database_url(settings))


def create_worker_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return WorkerRepository()
    from app.postgres.runtime import PostgresWorkerRepository
    return PostgresWorkerRepository(_database_url(settings))


def create_raw_snapshot_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return RawSnapshotRepository()
    from app.postgres.refresh import PostgresRawSnapshotRepository
    return PostgresRawSnapshotRepository(_database_url(settings))


def create_change_event_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return ChangeEventRepository()
    from app.postgres.refresh import PostgresChangeEventRepository
    return PostgresChangeEventRepository(_database_url(settings))


def create_refresh_run_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return RefreshRunRepository()
    from app.postgres.refresh import PostgresRefreshRunRepository
    return PostgresRefreshRunRepository(_database_url(settings))


def create_refresh_schedule_repository(
    settings: Settings | None = None,
) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        return RefreshScheduleRepository()
    from app.postgres.refresh import PostgresRefreshScheduleRepository
    return PostgresRefreshScheduleRepository(_database_url(settings))


def create_validation_repository(settings: Settings | None = None) -> Any:
    settings = _settings(settings)
    if settings.database_backend == "sqlite":
        from app.repositories.validation import SqliteValidationRepository
        return SqliteValidationRepository()
    from app.postgres.validation import PostgresValidationRepository
    return PostgresValidationRepository(_database_url(settings))
