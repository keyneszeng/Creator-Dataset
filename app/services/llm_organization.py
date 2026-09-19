from typing import Any

from app.core.settings import get_settings
from app.core.versioning import DATASET_SCHEMA_VERSION
from app.llm.crypto import decrypt_secret, encrypt_secret
from app.llm.models import LlmOrganizationTask
from app.llm.openai_compatible import OpenAICompatibleAdapter
from app.llm.security import validate_llm_base_url
from app.repositories.factory import (
    create_export_repository,
    create_job_repository,
    create_llm_repository,
    create_text_unit_repository,
)


class LlmOrganizationService:
    def __init__(
        self,
        *,
        repository: Any | None = None,
        text_units: Any | None = None,
        exports: Any | None = None,
        jobs: Any | None = None,
    ) -> None:
        self.repository = repository or create_llm_repository()
        self.text_units = text_units or create_text_unit_repository()
        self.exports = exports or create_export_repository()
        self.jobs = jobs or create_job_repository()

    def create_connection(
        self,
        *,
        user_id: int,
        provider: str,
        label: str,
        model: str,
        base_url: str,
        api_key: str,
    ) -> dict[str, Any]:
        settings = get_settings()
        if not settings.llm_enabled:
            raise ValueError("User-connected LLM support is disabled.")
        if provider != "openai_compatible":
            raise ValueError(
                "Only openai_compatible is supported in the first LLM adapter."
            )

        safe_url = validate_llm_base_url(
            base_url,
            settings=settings,
        )
        encrypted = encrypt_secret(
            api_key,
            key_text=settings.llm_credential_encryption_key,
        )
        return self.repository.create_connection(
            user_id=user_id,
            provider=provider,
            label=label,
            model=model,
            base_url=safe_url,
            secret_ciphertext=encrypted,
        )

    def create_run(
        self,
        *,
        user_id: int,
        post_id: str,
        connection_id: int,
        task: LlmOrganizationTask,
        custom_instruction: str | None,
    ) -> tuple[int, int]:
        connection = self.repository.get_connection(
            user_id=user_id,
            connection_id=connection_id,
        )
        if connection is None or not connection.get("enabled"):
            raise ValueError("Unknown or disabled LLM connection.")

        run_id = self.repository.create_run(
            user_id=user_id,
            post_id=post_id,
            connection_id=connection_id,
            task=task.value,
            custom_instruction=custom_instruction,
            input_schema_version=DATASET_SCHEMA_VERSION,
        )
        job_id = self.jobs.enqueue(
            job_type="LLM_ORGANIZE",
            post_id=post_id,
            idempotency_key=f"llm-organize:{run_id}",
            payload={"run_id": run_id},
            priority=150,
            max_attempts=3,
        )
        return run_id, job_id

    def execute_run(self, *, run_id: int) -> None:
        settings = get_settings()
        run = self.repository.get_run_for_worker(run_id=run_id)
        if run is None:
            raise ValueError(f"Unknown LLM organization run: {run_id}")
        if not run.get("enabled"):
            raise ValueError("LLM connection is disabled.")

        self.repository.mark_running(run_id=run_id)
        try:
            api_key = decrypt_secret(
                str(run["secret_ciphertext"]),
                key_text=settings.llm_credential_encryption_key,
            )
            base_url = validate_llm_base_url(
                str(run["base_url"]),
                settings=settings,
            )
            source_text = self._source_text(
                post_id=str(run["post_id"]),
                max_chars=settings.llm_max_input_chars,
            )
            task = LlmOrganizationTask(str(run["task"]))

            if str(run["provider"]) != "openai_compatible":
                raise ValueError(
                    f"Unsupported LLM provider: {run['provider']}"
                )

            adapter = OpenAICompatibleAdapter(base_url=base_url)
            result = adapter.organize(
                model=str(run["model"]),
                api_key=api_key,
                task=task,
                source_text=source_text,
                custom_instruction=run.get("custom_instruction"),
            )
            self.repository.mark_complete(
                run_id=run_id,
                result=result.model_dump(),
            )
        except Exception as exc:
            self.repository.mark_failed(
                run_id=run_id,
                error=str(exc),
            )
            raise

    def _source_text(
        self,
        *,
        post_id: str,
        max_chars: int,
    ) -> str:
        bundle = self.exports.get_post_bundle(post_id=post_id)
        if bundle is None:
            raise ValueError(f"Unknown post: {post_id}")

        post = bundle["post"]
        units = self.text_units.list_for_post(post_id=post_id)

        chunks = [
            f"TITLE: {post.get('title') or ''}",
            f"AUTHOR: {post.get('content') or ''}",
        ]
        for unit in units:
            chunks.append(
                f"{unit.get('unit_type')} | "
                f"{unit.get('provenance')}: "
                f"{unit.get('text') or ''}"
            )

        text = "\n\n".join(chunks)
        if len(text) > max_chars:
            text = text[:max_chars]
        return text
