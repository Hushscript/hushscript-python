from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.org_usage_response_group_by import (
    OrgUsageResponseGroupBy,
    check_org_usage_response_group_by,
)

if TYPE_CHECKING:
    from ..models.org_usage_row import OrgUsageRow


T = TypeVar("T", bound="OrgUsageResponse")


@_attrs_define
class OrgUsageResponse:
    """
    Attributes:
        rows (list[OrgUsageRow]):
        from_ (int):
        to (int):
        group_by (OrgUsageResponseGroupBy):
        rate_cents_per_hour (int):
    """

    rows: list[OrgUsageRow]
    from_: int
    to: int
    group_by: OrgUsageResponseGroupBy
    rate_cents_per_hour: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        rows = []
        for rows_item_data in self.rows:
            rows_item = rows_item_data.to_dict()
            rows.append(rows_item)

        from_ = self.from_

        to = self.to

        group_by: str = self.group_by

        rate_cents_per_hour = self.rate_cents_per_hour

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "rows": rows,
                "from": from_,
                "to": to,
                "group_by": group_by,
                "rate_cents_per_hour": rate_cents_per_hour,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.org_usage_row import OrgUsageRow  # noqa: PLC0415

        d = dict(src_dict)
        rows = []
        _rows = d.pop("rows")
        for rows_item_data in _rows:
            rows_item = OrgUsageRow.from_dict(rows_item_data)

            rows.append(rows_item)

        from_ = d.pop("from")

        to = d.pop("to")

        group_by = check_org_usage_response_group_by(d.pop("group_by"))

        rate_cents_per_hour = d.pop("rate_cents_per_hour")

        org_usage_response = cls(
            rows=rows,
            from_=from_,
            to=to,
            group_by=group_by,
            rate_cents_per_hour=rate_cents_per_hour,
        )

        org_usage_response.additional_properties = d
        return org_usage_response

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
