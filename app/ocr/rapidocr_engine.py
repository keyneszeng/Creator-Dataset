from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from app.core.errors import IntegrationNotInstalled
from app.ocr.base import OcrBlock, OcrResult


class RapidOcrEngine:
    name = "rapidocr"

    def __init__(self, *, language: str = "ch") -> None:
        self.language = language
        try:
            from rapidocr import RapidOCR
        except ImportError as exc:
            raise IntegrationNotInstalled(
                'Install OCR dependencies with pip install -e ".[ocr]".'
            ) from exc

        # RapidOCR 3.x exposes language through Rec.lang_type.
        self._engine = RapidOCR(params={"Rec.lang_type": language})

    def recognize(self, image_path: Path) -> OcrResult:
        output = self._engine(str(image_path))

        txts = list(getattr(output, "txts", None) or [])
        scores = list(getattr(output, "scores", None) or [])
        boxes = list(getattr(output, "boxes", None) or [])

        blocks: list[OcrBlock] = []
        valid_scores: list[float] = []

        for index, text in enumerate(txts):
            normalized_text = str(text).strip()
            if not normalized_text:
                continue

            score = None
            if index < len(scores) and scores[index] is not None:
                score = float(scores[index])
                valid_scores.append(score)

            box = None
            if index < len(boxes) and boxes[index] is not None:
                raw_box = boxes[index]
                box = [
                    [float(point[0]), float(point[1])]
                    for point in raw_box
                ]

            blocks.append(
                OcrBlock(
                    text=normalized_text,
                    confidence=score,
                    box=box,
                )
            )

        full_text = "\n".join(block.text for block in blocks)
        average_confidence = (
            sum(valid_scores) / len(valid_scores)
            if valid_scores
            else None
        )

        try:
            engine_version = version("rapidocr")
        except PackageNotFoundError:
            engine_version = None

        return OcrResult(
            full_text=full_text,
            blocks=blocks,
            average_confidence=average_confidence,
            engine=self.name,
            engine_version=engine_version,
            language=self.language,
        )
