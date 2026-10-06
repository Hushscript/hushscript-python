from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.active_hold_kind import ActiveHoldKind, check_active_hold_kind

T = TypeVar("T", bound="ActiveHold")


@_attrs_define
class ActiveHold:
    """
    Attributes:
        id (str):
        kind (ActiveHoldKind): Which kind of work reserved these seconds. The id is that work's own id and is unique
            only within its kind.
        seconds (int):
        created_at (int):
    """

    id: str
    kind: ActiveHoldKind
    seconds: int
    created_at: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        kind: str = self.kind

        seconds = self.seconds

        created_at = self.created_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "kind": kind,
                "seconds": seconds,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        kind = check_active_hold_kind(d.pop("kind"))

        seconds = d.pop("seconds")

        created_at = d.pop("created_at")

        active_hold = cls(
            id=id,
            kind=kind,
            seconds=seconds,
            created_at=created_at,
        )

        active_hold.additional_properties = d
        return active_hold

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
