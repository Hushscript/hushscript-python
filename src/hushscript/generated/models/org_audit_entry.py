from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgAuditEntry")


@_attrs_define
class OrgAuditEntry:
    """
    Attributes:
        id (int):
        actor_user_id (None | str):
        event (str):
        detail (None | str):
        created_at (int):
    """

    id: int
    actor_user_id: None | str
    event: str
    detail: None | str
    created_at: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        actor_user_id: None | str
        actor_user_id = self.actor_user_id

        event = self.event

        detail: None | str
        detail = self.detail

        created_at = self.created_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "actor_user_id": actor_user_id,
                "event": event,
                "detail": detail,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        def _parse_actor_user_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        actor_user_id = _parse_actor_user_id(d.pop("actor_user_id"))

        event = d.pop("event")

        def _parse_detail(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        detail = _parse_detail(d.pop("detail"))

        created_at = d.pop("created_at")

        org_audit_entry = cls(
            id=id,
            actor_user_id=actor_user_id,
            event=event,
            detail=detail,
            created_at=created_at,
        )

        org_audit_entry.additional_properties = d
        return org_audit_entry

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
