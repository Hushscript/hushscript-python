from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.upload_create_response_funding import (
    UploadCreateResponseFunding,
    check_upload_create_response_funding,
)

if TYPE_CHECKING:
    from ..models.upload_create_response_upload_type_0 import (
        UploadCreateResponseUploadType0,
    )
    from ..models.upload_limits import UploadLimits


T = TypeVar("T", bound="UploadCreateResponse")


@_attrs_define
class UploadCreateResponse:
    """
    Attributes:
        job_id (str):
        balance_seconds (int): The account's net balance after this upload's hold was placed.
        held_seconds (int):
        limits (UploadLimits): The caller's current upload admission limits, shared by every response that carries them.
        upload (None | UploadCreateResponseUploadType0): One page of presigned direct-to-R2 PUT URLs, or null when
            direct-to-R2 uploads are not available for this job and parts must be sent to upload_part instead.
        funding (UploadCreateResponseFunding): Which balance this upload's hold was placed against.
        state (str): The job's initial state, typically uploading.
    """

    job_id: str
    balance_seconds: int
    held_seconds: int
    limits: UploadLimits
    upload: None | UploadCreateResponseUploadType0
    funding: UploadCreateResponseFunding
    state: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.upload_create_response_upload_type_0 import (
            UploadCreateResponseUploadType0,  # noqa: PLC0415
        )

        job_id = self.job_id

        balance_seconds = self.balance_seconds

        held_seconds = self.held_seconds

        limits = self.limits.to_dict()

        upload: dict[str, Any] | None
        if isinstance(self.upload, UploadCreateResponseUploadType0):
            upload = self.upload.to_dict()
        else:
            upload = self.upload

        funding: str = self.funding

        state = self.state

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "job_id": job_id,
                "balance_seconds": balance_seconds,
                "held_seconds": held_seconds,
                "limits": limits,
                "upload": upload,
                "funding": funding,
                "state": state,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.upload_create_response_upload_type_0 import (
            UploadCreateResponseUploadType0,  # noqa: PLC0415
        )
        from ..models.upload_limits import UploadLimits  # noqa: PLC0415

        d = dict(src_dict)
        job_id = d.pop("job_id")

        balance_seconds = d.pop("balance_seconds")

        held_seconds = d.pop("held_seconds")

        limits = UploadLimits.from_dict(d.pop("limits"))

        def _parse_upload(data: object) -> None | UploadCreateResponseUploadType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                upload_type_0 = UploadCreateResponseUploadType0.from_dict(data)

                return upload_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UploadCreateResponseUploadType0, data)

        upload = _parse_upload(d.pop("upload"))

        funding = check_upload_create_response_funding(d.pop("funding"))

        state = d.pop("state")

        upload_create_response = cls(
            job_id=job_id,
            balance_seconds=balance_seconds,
            held_seconds=held_seconds,
            limits=limits,
            upload=upload,
            funding=funding,
            state=state,
        )

        upload_create_response.additional_properties = d
        return upload_create_response

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
