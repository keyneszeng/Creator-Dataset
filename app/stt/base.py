from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    average_logprob: float | None = None


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    full_text: str
    segments: list[TranscriptSegment]
    engine: str
    engine_version: str | None
    model: str
    language: str | None
    language_probability: float | None


class SttEngine(Protocol):
    name: str
    model_name: str

    def transcribe(self, media_path: Path) -> TranscriptResult:
        ...
