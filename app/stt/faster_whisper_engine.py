from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from app.core.errors import IntegrationNotInstalled
from app.stt.base import TranscriptResult, TranscriptSegment


class FasterWhisperEngine:
    name = "faster-whisper"

    def __init__(
        self,
        *,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = None,
    ) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise IntegrationNotInstalled(
                'Install STT dependencies with pip install -e ".[stt]".'
            ) from exc

        self.model_name = model_name
        self.language = language
        self._model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )

    def transcribe(self, media_path: Path) -> TranscriptResult:
        segments_iter, info = self._model.transcribe(
            str(media_path),
            language=self.language,
            vad_filter=True,
            beam_size=5,
        )

        segments: list[TranscriptSegment] = []
        texts: list[str] = []

        for segment in segments_iter:
            text = str(segment.text or "").strip()
            if not text:
                continue
            texts.append(text)
            segments.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=text,
                    average_logprob=(
                        float(segment.avg_logprob)
                        if getattr(segment, "avg_logprob", None) is not None
                        else None
                    ),
                )
            )

        try:
            engine_version = version("faster-whisper")
        except PackageNotFoundError:
            engine_version = None

        return TranscriptResult(
            full_text="\n".join(texts),
            segments=segments,
            engine=self.name,
            engine_version=engine_version,
            model=self.model_name,
            language=getattr(info, "language", None),
            language_probability=(
                float(info.language_probability)
                if getattr(info, "language_probability", None) is not None
                else None
            ),
        )
