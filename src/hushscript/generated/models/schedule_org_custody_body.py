from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.schedule_org_custody_body_custody import (
    ScheduleOrgCustodyBodyCustody,
    check_schedule_org_custody_body_custody,
)

T = TypeVar("T", bound="ScheduleOrgCustodyBody")


@_attrs_define
class ScheduleOrgCustodyBody:
    """
    Attributes:
        custody (ScheduleOrgCustodyBodyCustody): Must be firm; this route only schedules the private to firm switch.
    """

    custody: ScheduleOrgCustodyBodyCustody
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        custody: str = self.custody

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "custody": custody,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        custody = check_schedule_org_custody_body_custody(d.pop("custody"))

        schedule_org_custody_body = cls(
            custody=custody,
        )

        schedule_org_custody_body.additional_properties = d
        return schedule_org_custody_body

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
