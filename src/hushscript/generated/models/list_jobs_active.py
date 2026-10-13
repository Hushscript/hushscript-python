from typing import Literal

ListJobsActive = Literal["1", "true", "yes"]

LIST_JOBS_ACTIVE_VALUES: set[ListJobsActive] = {
    "1",
    "true",
    "yes",
}


def check_list_jobs_active(value: str) -> ListJobsActive:
    if value in LIST_JOBS_ACTIVE_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {LIST_JOBS_ACTIVE_VALUES!r}"
    )
