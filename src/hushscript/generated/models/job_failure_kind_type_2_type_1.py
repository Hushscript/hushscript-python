from typing import Literal

JobFailureKindType2Type1 = Literal["media_undecodable", "media_unreadable"]

JOB_FAILURE_KIND_TYPE_2_TYPE_1_VALUES: set[JobFailureKindType2Type1] = {
    "media_undecodable",
    "media_unreadable",
}


def check_job_failure_kind_type_2_type_1(value: str) -> JobFailureKindType2Type1:
    if value in JOB_FAILURE_KIND_TYPE_2_TYPE_1_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {JOB_FAILURE_KIND_TYPE_2_TYPE_1_VALUES!r}"
    )
