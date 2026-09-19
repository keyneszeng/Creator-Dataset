from app.ocr.base import OcrEngine
from app.ocr.rapidocr_engine import RapidOcrEngine


def create_ocr_engine(
    name: str = "rapidocr",
    *,
    language: str = "ch",
) -> OcrEngine:
    normalized = name.strip().lower()
    if normalized == "rapidocr":
        return RapidOcrEngine(language=language)
    raise ValueError(f"Unsupported OCR engine: {name}")
