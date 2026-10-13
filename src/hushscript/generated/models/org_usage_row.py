from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgUsageRow")


@_attrs_define
class OrgUsageRow:
    """
    Attributes:
        key (str): The member email, matter code or client code this row aggregates, or "(none)" for an unfiled job or a
            purged member.
        jobs (int):
        billed_seconds (int):
        cost_cents (int): billed_seconds priced at the workspace's rebill_rate_cents_per_hour, rounded up to the cent.
    """

    key: str
    jobs: int
    billed_seconds: int
    cost_cents: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        key = self.key

        jobs = self.jobs

        billed_seconds = self.billed_seconds

        cost_cents = self.cost_cents

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "key": key,
                "jobs": jobs,
                "billed_seconds": billed_seconds,
                "cost_cents": cost_cents,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        key = d.pop("key")

        jobs = d.pop("jobs")

        billed_seconds = d.pop("billed_seconds")

        cost_cents = d.pop("cost_cents")

        org_usage_row = cls(
            key=key,
            jobs=jobs,
            billed_seconds=billed_seconds,
            cost_cents=cost_cents,
        )

        org_usage_row.additional_properties = d
        return org_usage_row

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
