from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.transcript_envelope_translations import TranscriptEnvelopeTranslations
    from ..models.transcript_language import TranscriptLanguage


T = TypeVar("T", bound="TranscriptEnvelope")


@_attrs_define
class TranscriptEnvelope:
    """The transcript's full structured body.

    Attributes:
        version (int):
        original (TranscriptLanguage):
        translations (TranscriptEnvelopeTranslations): Keyed by target locale, plus the reserved key cleaned for the AI-
            rewritten cleaned body when one exists.
    """

    version: int
    original: TranscriptLanguage
    translations: TranscriptEnvelopeTranslations
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        version = self.version

        original = self.original.to_dict()

        translations = self.translations.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "version": version,
                "original": original,
                "translations": translations,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.transcript_envelope_translations import (
            TranscriptEnvelopeTranslations,  # noqa: PLC0415
        )
        from ..models.transcript_language import TranscriptLanguage  # noqa: PLC0415

        d = dict(src_dict)
        version = d.pop("version")

        original = TranscriptLanguage.from_dict(d.pop("original"))

        translations = TranscriptEnvelopeTranslations.from_dict(d.pop("translations"))

        transcript_envelope = cls(
            version=version,
            original=original,
            translations=translations,
        )

        transcript_envelope.additional_properties = d
        return transcript_envelope

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
