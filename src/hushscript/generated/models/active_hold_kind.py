from typing import Literal

ActiveHoldKind = Literal["insights", "qa", "transcription", "translation"]

ACTIVE_HOLD_KIND_VALUES: set[ActiveHoldKind] = {
    "insights",
    "qa",
    "transcription",
    "translation",
}


def check_active_hold_kind(value: str) -> ActiveHoldKind:
    if value in ACTIVE_HOLD_KIND_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {ACTIVE_HOLD_KIND_VALUES!r}"
    )
