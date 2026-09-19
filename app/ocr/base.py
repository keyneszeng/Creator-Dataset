from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class OcrBlock:
    text: str
    confidence: float | None
    box: list[list[float]] | None = None


@dataclass(frozen=True, slots=True)
class OcrResult:
    full_text: str
    blocks: list[OcrBlock]
    average_confidence: float | None
    engine: str
    engine_version: str | None
    language: str | None


class OcrEngine(Protocol):
    name: str

    def recognize(self, image_path: Path) -> OcrResult:
        ...
