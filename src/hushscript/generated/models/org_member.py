from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgMember")


@_attrs_define
class OrgMember:
    """
    Attributes:
        user_id (str):
        email (str):
        role (str):
        joined_at (int):
        is_admin (bool):
        is_billing (bool):
        is_reviewer (bool):
        monthly_cap_seconds (int | None): This member's own monthly seconds cap, or null when unset.
    """

    user_id: str
    email: str
    role: str
    joined_at: int
    is_admin: bool
    is_billing: bool
    is_reviewer: bool
    monthly_cap_seconds: int | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        user_id = self.user_id

        email = self.email

        role = self.role

        joined_at = self.joined_at

        is_admin = self.is_admin

        is_billing = self.is_billing

        is_reviewer = self.is_reviewer

        monthly_cap_seconds: int | None
        monthly_cap_seconds = self.monthly_cap_seconds

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "user_id": user_id,
                "email": email,
                "role": role,
                "joined_at": joined_at,
                "is_admin": is_admin,
                "is_billing": is_billing,
                "is_reviewer": is_reviewer,
                "monthly_cap_seconds": monthly_cap_seconds,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        user_id = d.pop("user_id")

        email = d.pop("email")

        role = d.pop("role")

        joined_at = d.pop("joined_at")

        is_admin = d.pop("is_admin")

        is_billing = d.pop("is_billing")

        is_reviewer = d.pop("is_reviewer")

        def _parse_monthly_cap_seconds(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        monthly_cap_seconds = _parse_monthly_cap_seconds(d.pop("monthly_cap_seconds"))

        org_member = cls(
            user_id=user_id,
            email=email,
            role=role,
            joined_at=joined_at,
            is_admin=is_admin,
            is_billing=is_billing,
            is_reviewer=is_reviewer,
            monthly_cap_seconds=monthly_cap_seconds,
        )

        org_member.additional_properties = d
        return org_member

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
