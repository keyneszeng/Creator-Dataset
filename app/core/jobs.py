from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from random import random


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class JobType(StrEnum):
    CREATOR_DISCOVERY = "CREATOR_DISCOVERY"
    CREATOR_REFRESH = "CREATOR_REFRESH"
    POST_DISCOVERY = "POST_DISCOVERY"
    POST_DETAIL = "POST_DETAIL"
    MEDIA_DOWNLOAD = "MEDIA_DOWNLOAD"
    OCR = "OCR"
    STT = "STT"
    ROOT_COMMENTS = "ROOT_COMMENTS"
    COMMENTS = "COMMENTS"
    SUB_COMMENTS = "SUB_COMMENTS"
    EXPORT = "EXPORT"
    VALIDATION = "VALIDATION"
    CREATOR_PIPELINE = "CREATOR_PIPELINE"
    POST_PIPELINE = "POST_PIPELINE"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    base_seconds: int = 10
    max_seconds: int = 1800
    jitter_ratio: float = 0.2

    def next_retry_at(self, attempt: int) -> datetime:
        exponent = max(attempt - 1, 0)
        delay = min(self.base_seconds * (2 ** exponent), self.max_seconds)
        jitter = delay * self.jitter_ratio * random()
        return datetime.now(timezone.utc) + timedelta(seconds=delay + jitter)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
