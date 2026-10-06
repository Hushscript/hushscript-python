from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgTranscript")


@_attrs_define
class OrgTranscript:
    """One row of the organization's firm-custody transcript index. Never carries transcript body or content beyond the
    title.

        Attributes:
            id (str):
            title (str):
            created_at (int):
            duration_seconds (int):
            user_id (str): The transcript owner's user id.
            legal_hold (bool):
    """

    id: str
    title: str
    created_at: int
    duration_seconds: int
    user_id: str
    legal_hold: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        title = self.title

        created_at = self.created_at

        duration_seconds = self.duration_seconds

        user_id = self.user_id

        legal_hold = self.legal_hold

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "title": title,
                "created_at": created_at,
                "duration_seconds": duration_seconds,
                "user_id": user_id,
                "legal_hold": legal_hold,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        title = d.pop("title")

        created_at = d.pop("created_at")

        duration_seconds = d.pop("duration_seconds")

        user_id = d.pop("user_id")

        legal_hold = d.pop("legal_hold")

        org_transcript = cls(
            id=id,
            title=title,
            created_at=created_at,
            duration_seconds=duration_seconds,
            user_id=user_id,
            legal_hold=legal_hold,
        )

        org_transcript.additional_properties = d
        return org_transcript

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
