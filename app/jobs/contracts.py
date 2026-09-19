from typing import Any, Protocol


class DurableJobRepository(Protocol):
    def enqueue(
        self,
        *,
        job_type: str,
        platform: str | None = None,
        creator_id: str | None = None,
        post_id: str | None = None,
        comment_id: str | None = None,
        parent_job_id: int | None = None,
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
        priority: int = 100,
        max_attempts: int = 5,
        depends_on: list[int] | None = None,
    ) -> int:
        ...

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> dict[str, Any] | None:
        ...

    def heartbeat(
        self,
        *,
        job_id: int,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> bool:
        ...

    def recover_expired_leases(self) -> int:
        ...

    def resolve_failed_dependencies(self) -> int:
        ...

    def schedule_retry(
        self,
        *,
        job_id: int,
        error: str,
        next_retry_at: str,
    ) -> None:
        ...

    def mark_waiting(self, *, job_id: int) -> None:
        ...

    def mark_complete(self, *, job_id: int) -> None:
        ...

    def mark_failed(
        self,
        *,
        job_id: int,
        error: str,
        status: str = "FAILED",
    ) -> None:
        ...

    def get(self, *, job_id: int) -> dict[str, Any] | None:
        ...

    def reconcile_ancestors(self, *, job_id: int) -> None:
        ...
