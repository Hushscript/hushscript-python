from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateUploadBodyTranscriptionOptionsType0")


@_attrs_define
class CreateUploadBodyTranscriptionOptionsType0:
    """Transcription options for this job. Every field is optional; omitting the object requests the account's default
    behaviour (language auto-detection and speaker labels on).

        Attributes:
            language_code (None | str | Unset): Force a specific spoken language instead of auto-detection.
            speaker_detection (bool | Unset): Label distinct speakers in the transcript. Forced on automatically when
                translation_targets is non-empty.
            keyterms_prompt (list[str] | Unset): Domain vocabulary to bias transcription toward, up to 1000 terms of at most
                6 words each.
            prompt (None | str | Unset): Free-text context to bias transcription toward.
            medical_mode (bool | Unset): Bill and transcribe as a medical dictation. Requires language_code to be one of en,
                es, fr, de; billed at a 100 percent surcharge on the duration.
            multichannel (bool | Unset): Transcribe each audio channel independently. Billed per channel: a stereo file
                counts twice, a 3-channel file three times, up to 8 channels, and the medical surcharge applies on top of that;
                translation targets stay on a single duration. The channel count is the most channels any audio track of the
                file carries. A file with more than 8 channels, or one whose channel count cannot be read, falls back to mixed
                audio with speaker labels and is billed once. Without this option the file is transcribed as one mixed channel
                and billed once. The initial hold at upload creation is for a single channel; verification raises it to the per-
                channel amount and fails the job with insufficient_balance if the balance cannot cover it.
            translation_targets (list[str] | Unset): Locales to additionally translate the transcript into. Each target adds
                a 25 percent surcharge on the duration and forces speaker_detection on.
            auto_generate_insights (bool | None | Unset): Override the account's automatic-Insights default for this upload
                alone. Omit to inherit the account default; an explicit false always suppresses automatic generation for this
                upload.
    """

    language_code: None | str | Unset = UNSET
    speaker_detection: bool | Unset = UNSET
    keyterms_prompt: list[str] | Unset = UNSET
    prompt: None | str | Unset = UNSET
    medical_mode: bool | Unset = UNSET
    multichannel: bool | Unset = UNSET
    translation_targets: list[str] | Unset = UNSET
    auto_generate_insights: bool | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        language_code: None | str | Unset
        if isinstance(self.language_code, Unset):
            language_code = UNSET
        else:
            language_code = self.language_code

        speaker_detection = self.speaker_detection

        keyterms_prompt: list[str] | Unset = UNSET
        if not isinstance(self.keyterms_prompt, Unset):
            keyterms_prompt = self.keyterms_prompt

        prompt: None | str | Unset
        if isinstance(self.prompt, Unset):
            prompt = UNSET
        else:
            prompt = self.prompt

        medical_mode = self.medical_mode

        multichannel = self.multichannel

        translation_targets: list[str] | Unset = UNSET
        if not isinstance(self.translation_targets, Unset):
            translation_targets = self.translation_targets

        auto_generate_insights: bool | None | Unset
        if isinstance(self.auto_generate_insights, Unset):
            auto_generate_insights = UNSET
        else:
            auto_generate_insights = self.auto_generate_insights

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if language_code is not UNSET:
            field_dict["language_code"] = language_code
        if speaker_detection is not UNSET:
            field_dict["speaker_detection"] = speaker_detection
        if keyterms_prompt is not UNSET:
            field_dict["keyterms_prompt"] = keyterms_prompt
        if prompt is not UNSET:
            field_dict["prompt"] = prompt
        if medical_mode is not UNSET:
            field_dict["medical_mode"] = medical_mode
        if multichannel is not UNSET:
            field_dict["multichannel"] = multichannel
        if translation_targets is not UNSET:
            field_dict["translation_targets"] = translation_targets
        if auto_generate_insights is not UNSET:
            field_dict["auto_generate_insights"] = auto_generate_insights

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_language_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        language_code = _parse_language_code(d.pop("language_code", UNSET))

        speaker_detection = d.pop("speaker_detection", UNSET)

        keyterms_prompt = cast(list[str], d.pop("keyterms_prompt", UNSET))

        def _parse_prompt(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        prompt = _parse_prompt(d.pop("prompt", UNSET))

        medical_mode = d.pop("medical_mode", UNSET)

        multichannel = d.pop("multichannel", UNSET)

        translation_targets = cast(list[str], d.pop("translation_targets", UNSET))

        def _parse_auto_generate_insights(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        auto_generate_insights = _parse_auto_generate_insights(
            d.pop("auto_generate_insights", UNSET)
        )

        create_upload_body_transcription_options_type_0 = cls(
            language_code=language_code,
            speaker_detection=speaker_detection,
            keyterms_prompt=keyterms_prompt,
            prompt=prompt,
            medical_mode=medical_mode,
            multichannel=multichannel,
            translation_targets=translation_targets,
            auto_generate_insights=auto_generate_insights,
        )

        create_upload_body_transcription_options_type_0.additional_properties = d
        return create_upload_body_transcription_options_type_0

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
