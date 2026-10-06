from typing import Literal

JobFailureKindType3Type1 = Literal["media_undecodable", "media_unreadable"]

JOB_FAILURE_KIND_TYPE_3_TYPE_1_VALUES: set[JobFailureKindType3Type1] = {
    "media_undecodable",
    "media_unreadable",
}


def check_job_failure_kind_type_3_type_1(value: str) -> JobFailureKindType3Type1:
    if value in JOB_FAILURE_KIND_TYPE_3_TYPE_1_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {JOB_FAILURE_KIND_TYPE_3_TYPE_1_VALUES!r}"
    )
