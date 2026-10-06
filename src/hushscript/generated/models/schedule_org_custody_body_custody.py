from typing import Literal

ScheduleOrgCustodyBodyCustody = Literal["firm"]

SCHEDULE_ORG_CUSTODY_BODY_CUSTODY_VALUES: set[ScheduleOrgCustodyBodyCustody] = {
    "firm",
}


def check_schedule_org_custody_body_custody(
    value: str,
) -> ScheduleOrgCustodyBodyCustody:
    if value in SCHEDULE_ORG_CUSTODY_BODY_CUSTODY_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {SCHEDULE_ORG_CUSTODY_BODY_CUSTODY_VALUES!r}"
    )
