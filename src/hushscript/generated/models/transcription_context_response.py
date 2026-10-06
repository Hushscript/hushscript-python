from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.context_dictionary import ContextDictionary
    from ..models.context_prompt_preset import ContextPromptPreset


T = TypeVar("T", bound="TranscriptionContextResponse")


@_attrs_define
class TranscriptionContextResponse:
    """Not paginated and carrying no cursor: both collections are capped when they are written (50 dictionaries, 20 prompt
    presets), so this response is always complete.

        Attributes:
            dictionaries (list[ContextDictionary]):
            prompts (list[ContextPromptPreset]):
    """

    dictionaries: list[ContextDictionary]
    prompts: list[ContextPromptPreset]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        dictionaries = []
        for dictionaries_item_data in self.dictionaries:
            dictionaries_item = dictionaries_item_data.to_dict()
            dictionaries.append(dictionaries_item)

        prompts = []
        for prompts_item_data in self.prompts:
            prompts_item = prompts_item_data.to_dict()
            prompts.append(prompts_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "dictionaries": dictionaries,
                "prompts": prompts,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.context_dictionary import ContextDictionary  # noqa: PLC0415
        from ..models.context_prompt_preset import ContextPromptPreset  # noqa: PLC0415

        d = dict(src_dict)
        dictionaries = []
        _dictionaries = d.pop("dictionaries")
        for dictionaries_item_data in _dictionaries:
            dictionaries_item = ContextDictionary.from_dict(dictionaries_item_data)

            dictionaries.append(dictionaries_item)

        prompts = []
        _prompts = d.pop("prompts")
        for prompts_item_data in _prompts:
            prompts_item = ContextPromptPreset.from_dict(prompts_item_data)

            prompts.append(prompts_item)

        transcription_context_response = cls(
            dictionaries=dictionaries,
            prompts=prompts,
        )

        transcription_context_response.additional_properties = d
        return transcription_context_response

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
