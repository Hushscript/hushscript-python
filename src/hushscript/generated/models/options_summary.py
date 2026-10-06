from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OptionsSummary")


@_attrs_define
class OptionsSummary:
    """A content-free summary of the transcription options a job was submitted with: what was requested, never the free-
    text content itself.

        Attributes:
            language_code (None | str): The manually forced language, or null if language auto-detection was used.
            speaker_detection (bool):
            medical_mode (bool):
            multichannel (bool):
            translation_targets (list[str]):
            keyterms (bool): Whether a keyterms prompt was set. The terms themselves are not included.
            prompt (bool): Whether a free-text context prompt was set. The prompt itself is not included.
            auto_generate_insights (bool | None): This upload's override of automatic Insights generation, or null if it
                used the account default.
    """

    language_code: None | str
    speaker_detection: bool
    medical_mode: bool
    multichannel: bool
    translation_targets: list[str]
    keyterms: bool
    prompt: bool
    auto_generate_insights: bool | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        language_code: None | str
        language_code = self.language_code

        speaker_detection = self.speaker_detection

        medical_mode = self.medical_mode

        multichannel = self.multichannel

        translation_targets = self.translation_targets

        keyterms = self.keyterms

        prompt = self.prompt

        auto_generate_insights: bool | None
        auto_generate_insights = self.auto_generate_insights

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "language_code": language_code,
                "speaker_detection": speaker_detection,
                "medical_mode": medical_mode,
                "multichannel": multichannel,
                "translation_targets": translation_targets,
                "keyterms": keyterms,
                "prompt": prompt,
                "auto_generate_insights": auto_generate_insights,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_language_code(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        language_code = _parse_language_code(d.pop("language_code"))

        speaker_detection = d.pop("speaker_detection")

        medical_mode = d.pop("medical_mode")

        multichannel = d.pop("multichannel")

        translation_targets = cast(list[str], d.pop("translation_targets"))

        keyterms = d.pop("keyterms")

        prompt = d.pop("prompt")

        def _parse_auto_generate_insights(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        auto_generate_insights = _parse_auto_generate_insights(
            d.pop("auto_generate_insights")
        )

        options_summary = cls(
            language_code=language_code,
            speaker_detection=speaker_detection,
            medical_mode=medical_mode,
            multichannel=multichannel,
            translation_targets=translation_targets,
            keyterms=keyterms,
            prompt=prompt,
            auto_generate_insights=auto_generate_insights,
        )

        options_summary.additional_properties = d
        return options_summary

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
