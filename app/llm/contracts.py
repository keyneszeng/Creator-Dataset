from typing import Protocol

from app.llm.models import (
    LlmOrganizationTask,
    SimplifiedDatasetResult,
)


class LlmProviderAdapter(Protocol):
    provider: str

    def organize(
        self,
        *,
        model: str,
        api_key: str,
        task: LlmOrganizationTask,
        source_text: str,
        custom_instruction: str | None = None,
    ) -> SimplifiedDatasetResult:
        ...


class LlmNotConfigured(RuntimeError):
    pass
