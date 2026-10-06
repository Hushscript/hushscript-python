from typing import Literal

TranscriptListRowInsightsState = Literal["failed", "generating", "none", "ready"]

TRANSCRIPT_LIST_ROW_INSIGHTS_STATE_VALUES: set[TranscriptListRowInsightsState] = {
    "failed",
    "generating",
    "none",
    "ready",
}


def check_transcript_list_row_insights_state(
    value: str,
) -> TranscriptListRowInsightsState:
    if value in TRANSCRIPT_LIST_ROW_INSIGHTS_STATE_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {TRANSCRIPT_LIST_ROW_INSIGHTS_STATE_VALUES!r}"
    )
