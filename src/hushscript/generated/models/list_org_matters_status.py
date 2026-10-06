from typing import Literal

ListOrgMattersStatus = Literal["closed", "open"]

LIST_ORG_MATTERS_STATUS_VALUES: set[ListOrgMattersStatus] = {
    "closed",
    "open",
}


def check_list_org_matters_status(value: str) -> ListOrgMattersStatus:
    if value in LIST_ORG_MATTERS_STATUS_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {LIST_ORG_MATTERS_STATUS_VALUES!r}"
    )
