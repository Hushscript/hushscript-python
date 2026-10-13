from typing import Literal

OrgUsageReportGroupBy = Literal["client", "matter", "member"]

ORG_USAGE_REPORT_GROUP_BY_VALUES: set[OrgUsageReportGroupBy] = {
    "client",
    "matter",
    "member",
}


def check_org_usage_report_group_by(value: str) -> OrgUsageReportGroupBy:
    if value in ORG_USAGE_REPORT_GROUP_BY_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {ORG_USAGE_REPORT_GROUP_BY_VALUES!r}"
    )
