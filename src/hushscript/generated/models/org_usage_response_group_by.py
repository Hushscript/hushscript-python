from typing import Literal

OrgUsageResponseGroupBy = Literal["client", "matter", "member"]

ORG_USAGE_RESPONSE_GROUP_BY_VALUES: set[OrgUsageResponseGroupBy] = {
    "client",
    "matter",
    "member",
}


def check_org_usage_response_group_by(value: str) -> OrgUsageResponseGroupBy:
    if value in ORG_USAGE_RESPONSE_GROUP_BY_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {ORG_USAGE_RESPONSE_GROUP_BY_VALUES!r}"
    )
