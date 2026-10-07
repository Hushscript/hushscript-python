"""What the friendly layer reads from each 2xx body, checked before any field is touched.

The tables list the fields the mappers use (`openapi.json` is the reference); keys they do not
list pass through, so a newer API still parses.
"""

from __future__ import annotations

from typing import Final

from ._shape import (
    Shape,
    anything,
    array_of,
    boolean,
    count,
    integer,
    nullable,
    number,
    object_of,
    record_of,
    string,
    timestamp,
)

UPLOAD_LIMITS: Final[Shape] = object_of(
    {
        "max_daily_seconds": count,
        "max_active_jobs": count,
        "active_jobs": count,
        "used_today_seconds": count,
    }
)

# `purchases_remaining_in_window` is in the body for agent accounts only, and not yet in the schema.
BALANCE: Final[Shape] = object_of(
    {"balance_seconds": integer, "held_seconds": count},
    {
        "credits_expire_at": nullable(timestamp),
        "purchases_remaining_in_window": nullable(count),
    },
)

ACCOUNT: Final[Shape] = object_of(
    {
        "balance_seconds": integer,
        "held_seconds": count,
        "credits_expire_at": nullable(timestamp),
        "card_on_file": boolean,
        "data_region": string,
        "limits": UPLOAD_LIMITS,
    },
    {"purchases_remaining_in_window": nullable(count)},
)

OPTIONS_SUMMARY: Final[Shape] = object_of(
    {
        "language_code": nullable(string),
        "speaker_detection": boolean,
        "medical_mode": boolean,
        "multichannel": boolean,
        "translation_targets": array_of(string),
        "keyterms": boolean,
        "prompt": boolean,
        "auto_generate_insights": nullable(boolean),
    }
)

JOB: Final[Shape] = object_of(
    {
        "id": string,
        "state": string,
        "mode": string,
        "declared_seconds": nullable(count),
        "verified_seconds": nullable(count),
        "actual_seconds": nullable(count),
        "billable_seconds": nullable(count),
        "error": nullable(string),
        "failure_kind": nullable(string),
        "retry_of": nullable(string),
        "created_at": timestamp,
        "transcript_id": nullable(string),
        "options": OPTIONS_SUMMARY,
    }
)

JOB_LIST: Final[Shape] = object_of({"jobs": array_of(JOB), "next_cursor": nullable(string)})

_UTTERANCE: Final[Shape] = object_of(
    {"speaker": string, "start_ms": number, "end_ms": number, "text": string}
)
_TRANSCRIPT_LANGUAGE: Final[Shape] = object_of({"utterances": array_of(_UTTERANCE)})

TRANSCRIPT_DETAIL: Final[Shape] = object_of(
    {
        "id": string,
        "title": string,
        "language_detected": nullable(string),
        "duration_seconds": count,
        "speaker_names": record_of(string),
        "tags": array_of(string),
        "created_at": timestamp,
        "updated_at": timestamp,
        "auto_delete_at": nullable(timestamp),
        "edited": boolean,
        "body": object_of(
            {"original": _TRANSCRIPT_LANGUAGE, "translations": record_of(_TRANSCRIPT_LANGUAGE)}
        ),
    }
)

TRANSCRIPT_LIST: Final[Shape] = object_of(
    {
        "transcripts": array_of(
            object_of(
                {
                    "id": string,
                    "title": string,
                    "language_detected": nullable(string),
                    "duration_seconds": count,
                    "created_at": timestamp,
                    "auto_delete_at": nullable(timestamp),
                    "tags": array_of(string),
                }
            )
        ),
        "next_cursor": nullable(string),
    }
)

DELETED_LIST: Final[Shape] = object_of(
    {
        "deleted": array_of(
            object_of(
                {
                    "id": string,
                    "title": string,
                    "duration_seconds": count,
                    "created_at": timestamp,
                    "deleted_at": timestamp,
                    "cause": string,
                    "receipt": nullable(record_of(anything)),
                }
            )
        ),
        "next_cursor": nullable(string),
    }
)
