from enum import StrEnum

from pydantic import BaseModel, Field


class LlmOrganizationTask(StrEnum):
    SIMPLIFY = "simplify"
    SUMMARIZE = "summarize"
    EXTRACT_KNOWLEDGE = "extract_knowledge"
    COMMENT_INSIGHTS = "comment_insights"
    CUSTOM = "custom"


class SimplifiedDatasetResult(BaseModel):
    """
    User-facing result.

    This intentionally hides raw crawling/OCR/STT implementation details.
    Provenance remains available separately for advanced/admin use.
    """

    title: str = ""
    summary: str = Field(default="", max_length=4000)
    key_points: list[str] = Field(default_factory=list, max_length=20)
    topics: list[str] = Field(default_factory=list, max_length=20)
    useful_facts: list[str] = Field(default_factory=list, max_length=30)
    audience_questions: list[str] = Field(default_factory=list, max_length=20)
    comment_insights: list[str] = Field(default_factory=list, max_length=20)
    action_items: list[str] = Field(default_factory=list, max_length=20)
    caveats: list[str] = Field(default_factory=list, max_length=20)
    language: str | None = None


class LlmConnectionPublic(BaseModel):
    id: int
    provider: str
    model: str
    label: str
    enabled: bool
