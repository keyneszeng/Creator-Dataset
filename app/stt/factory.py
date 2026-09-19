from app.stt.base import SttEngine
from app.stt.faster_whisper_engine import FasterWhisperEngine


def create_stt_engine(
    name: str = "faster-whisper",
    *,
    model_name: str = "small",
    language: str | None = None,
) -> SttEngine:
    normalized = name.strip().lower()
    if normalized == "faster-whisper":
        return FasterWhisperEngine(
            model_name=model_name,
            device="cpu",
            compute_type="int8",
            language=language,
        )
    raise ValueError(f"Unsupported STT engine: {name}")
