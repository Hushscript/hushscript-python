from typing import Literal

OrgMatterStatus = Literal["closed", "open"]

ORG_MATTER_STATUS_VALUES: set[OrgMatterStatus] = {
    "closed",
    "open",
}


def check_org_matter_status(value: str) -> OrgMatterStatus:
    if value in ORG_MATTER_STATUS_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {ORG_MATTER_STATUS_VALUES!r}"
    )
