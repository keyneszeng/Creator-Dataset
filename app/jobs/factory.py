from app.core.repositories import JobRepository
from app.core.settings import Settings, get_settings
from app.jobs.contracts import DurableJobRepository
from app.postgres.jobs import PostgresJobRepository


def create_job_repository(
    settings: Settings | None = None,
) -> DurableJobRepository:
    settings = settings or get_settings()

    if settings.database_backend == "sqlite":
        return JobRepository()

    if settings.database_backend == "postgres":
        if not settings.database_url:
            raise ValueError(
                "database_url is required when database_backend=postgres"
            )
        return PostgresJobRepository(settings.database_url)

    raise ValueError(
        f"Unsupported database backend: {settings.database_backend}"
    )
