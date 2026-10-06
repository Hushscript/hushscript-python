from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.utterance import Utterance


T = TypeVar("T", bound="TranscriptLanguage")


@_attrs_define
class TranscriptLanguage:
    """
    Attributes:
        utterances (list[Utterance]):
    """

    utterances: list[Utterance]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        utterances = []
        for utterances_item_data in self.utterances:
            utterances_item = utterances_item_data.to_dict()
            utterances.append(utterances_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "utterances": utterances,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.utterance import Utterance  # noqa: PLC0415

        d = dict(src_dict)
        utterances = []
        _utterances = d.pop("utterances")
        for utterances_item_data in _utterances:
            utterances_item = Utterance.from_dict(utterances_item_data)

            utterances.append(utterances_item)

        transcript_language = cls(
            utterances=utterances,
        )

        transcript_language.additional_properties = d
        return transcript_language

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
