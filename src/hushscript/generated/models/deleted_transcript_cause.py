from typing import Literal

DeletedTranscriptCause = Literal["dormant", "expired", "manual", "scheduled"]

DELETED_TRANSCRIPT_CAUSE_VALUES: set[DeletedTranscriptCause] = {
    "dormant",
    "expired",
    "manual",
    "scheduled",
}


def check_deleted_transcript_cause(value: str) -> DeletedTranscriptCause:
    if value in DELETED_TRANSCRIPT_CAUSE_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {DELETED_TRANSCRIPT_CAUSE_VALUES!r}"
    )
