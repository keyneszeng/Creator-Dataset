import json

import httpx

from app.llm.models import (
    LlmOrganizationTask,
    SimplifiedDatasetResult,
)


class OpenAICompatibleAdapter:
    provider = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def organize(
        self,
        *,
        model: str,
        api_key: str,
        task: LlmOrganizationTask,
        source_text: str,
        custom_instruction: str | None = None,
    ) -> SimplifiedDatasetResult:
        instruction = self._instruction(
            task=task,
            custom_instruction=custom_instruction,
        )
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You organize a Creator Dataset into a concise "
                            "user-facing result. Do not invent facts. "
                            "Return one valid JSON object only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"{instruction}\n\n"
                            "Return an object with keys: title, summary, "
                            "key_points, topics, useful_facts, "
                            "audience_questions, comment_insights, "
                            "action_items, caveats, language.\n\n"
                            f"DATASET:\n{source_text}"
                        ),
                    },
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = str(
            payload["choices"][0]["message"]["content"]
        ).strip()
        parsed = json.loads(content)
        return SimplifiedDatasetResult.model_validate(parsed)

    def _instruction(
        self,
        *,
        task: LlmOrganizationTask,
        custom_instruction: str | None,
    ) -> str:
        if task == LlmOrganizationTask.SIMPLIFY:
            return (
                "Create a short, plain-language overview. Prioritize what "
                "a normal user needs to understand quickly."
            )
        if task == LlmOrganizationTask.SUMMARIZE:
            return "Summarize the Creator Post and its supporting evidence."
        if task == LlmOrganizationTask.EXTRACT_KNOWLEDGE:
            return (
                "Extract reusable knowledge, facts, methods and practical "
                "takeaways. Separate uncertainty into caveats."
            )
        if task == LlmOrganizationTask.COMMENT_INSIGHTS:
            return (
                "Focus on audience questions, disagreements, repeated needs "
                "and useful insights from comments."
            )
        if task == LlmOrganizationTask.CUSTOM:
            if not custom_instruction:
                raise ValueError(
                    "custom_instruction is required for custom organization."
                )
            return custom_instruction
        raise ValueError(f"Unsupported LLM organization task: {task}")
