from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Utterance")


@_attrs_define
class Utterance:
    """
    Attributes:
        speaker (str):
        start_ms (int):
        end_ms (int):
        text (str):
    """

    speaker: str
    start_ms: int
    end_ms: int
    text: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        speaker = self.speaker

        start_ms = self.start_ms

        end_ms = self.end_ms

        text = self.text

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "speaker": speaker,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        speaker = d.pop("speaker")

        start_ms = d.pop("start_ms")

        end_ms = d.pop("end_ms")

        text = d.pop("text")

        utterance = cls(
            speaker=speaker,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text,
        )

        utterance.additional_properties = d
        return utterance

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
