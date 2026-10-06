from typing import Literal

OrgUsageReportCsvGroupBy = Literal["client", "matter", "member"]

ORG_USAGE_REPORT_CSV_GROUP_BY_VALUES: set[OrgUsageReportCsvGroupBy] = {
    "client",
    "matter",
    "member",
}


def check_org_usage_report_csv_group_by(value: str) -> OrgUsageReportCsvGroupBy:
    if value in ORG_USAGE_REPORT_CSV_GROUP_BY_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {ORG_USAGE_REPORT_CSV_GROUP_BY_VALUES!r}"
    )
