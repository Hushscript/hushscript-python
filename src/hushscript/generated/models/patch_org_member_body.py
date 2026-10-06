from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchOrgMemberBody")


@_attrs_define
class PatchOrgMemberBody:
    """
    Attributes:
        is_admin (bool | Unset): Grant or revoke the admin right. Omit to leave unchanged.
        is_billing (bool | Unset): Grant or revoke the billing right. Omit to leave unchanged.
        is_reviewer (bool | Unset): Grant or revoke the reviewer right. Omit to leave unchanged.
        monthly_cap_seconds (int | None | Unset): The member's monthly spend cap in seconds against the pool, or null to
            clear it. Omit to leave unchanged.
    """

    is_admin: bool | Unset = UNSET
    is_billing: bool | Unset = UNSET
    is_reviewer: bool | Unset = UNSET
    monthly_cap_seconds: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        is_admin = self.is_admin

        is_billing = self.is_billing

        is_reviewer = self.is_reviewer

        monthly_cap_seconds: int | None | Unset
        if isinstance(self.monthly_cap_seconds, Unset):
            monthly_cap_seconds = UNSET
        else:
            monthly_cap_seconds = self.monthly_cap_seconds

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if is_admin is not UNSET:
            field_dict["is_admin"] = is_admin
        if is_billing is not UNSET:
            field_dict["is_billing"] = is_billing
        if is_reviewer is not UNSET:
            field_dict["is_reviewer"] = is_reviewer
        if monthly_cap_seconds is not UNSET:
            field_dict["monthly_cap_seconds"] = monthly_cap_seconds

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        is_admin = d.pop("is_admin", UNSET)

        is_billing = d.pop("is_billing", UNSET)

        is_reviewer = d.pop("is_reviewer", UNSET)

        def _parse_monthly_cap_seconds(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        monthly_cap_seconds = _parse_monthly_cap_seconds(
            d.pop("monthly_cap_seconds", UNSET)
        )

        patch_org_member_body = cls(
            is_admin=is_admin,
            is_billing=is_billing,
            is_reviewer=is_reviewer,
            monthly_cap_seconds=monthly_cap_seconds,
        )

        patch_org_member_body.additional_properties = d
        return patch_org_member_body

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
