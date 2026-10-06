from typing import Literal

UploadCreateResponseFunding = Literal["org", "personal"]

UPLOAD_CREATE_RESPONSE_FUNDING_VALUES: set[UploadCreateResponseFunding] = {
    "org",
    "personal",
}


def check_upload_create_response_funding(value: str) -> UploadCreateResponseFunding:
    if value in UPLOAD_CREATE_RESPONSE_FUNDING_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {UPLOAD_CREATE_RESPONSE_FUNDING_VALUES!r}"
    )
