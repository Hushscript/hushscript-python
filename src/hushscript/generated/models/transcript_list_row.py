from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.transcript_list_row_insights_state import (
    TranscriptListRowInsightsState,
    check_transcript_list_row_insights_state,
)

if TYPE_CHECKING:
    from ..models.options_summary import OptionsSummary


T = TypeVar("T", bound="TranscriptListRow")


@_attrs_define
class TranscriptListRow:
    """
    Attributes:
        id (str):
        title (str):
        language_detected (None | str):
        duration_seconds (int):
        created_at (int):
        auto_delete_at (int | None):
        tags (list[str]):
        options (OptionsSummary): A content-free summary of the transcription options a job was submitted with: what was
            requested, never the free-text content itself.
        insights_state (TranscriptListRowInsightsState): A display hint only, never an authority on whether Insights may
            be generated or charged for.
    """

    id: str
    title: str
    language_detected: None | str
    duration_seconds: int
    created_at: int
    auto_delete_at: int | None
    tags: list[str]
    options: OptionsSummary
    insights_state: TranscriptListRowInsightsState
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        title = self.title

        language_detected: None | str
        language_detected = self.language_detected

        duration_seconds = self.duration_seconds

        created_at = self.created_at

        auto_delete_at: int | None
        auto_delete_at = self.auto_delete_at

        tags = self.tags

        options = self.options.to_dict()

        insights_state: str = self.insights_state

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "title": title,
                "language_detected": language_detected,
                "duration_seconds": duration_seconds,
                "created_at": created_at,
                "auto_delete_at": auto_delete_at,
                "tags": tags,
                "options": options,
                "insights_state": insights_state,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.options_summary import OptionsSummary  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        title = d.pop("title")

        def _parse_language_detected(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        language_detected = _parse_language_detected(d.pop("language_detected"))

        duration_seconds = d.pop("duration_seconds")

        created_at = d.pop("created_at")

        def _parse_auto_delete_at(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        auto_delete_at = _parse_auto_delete_at(d.pop("auto_delete_at"))

        tags = cast(list[str], d.pop("tags"))

        options = OptionsSummary.from_dict(d.pop("options"))

        insights_state = check_transcript_list_row_insights_state(
            d.pop("insights_state")
        )

        transcript_list_row = cls(
            id=id,
            title=title,
            language_detected=language_detected,
            duration_seconds=duration_seconds,
            created_at=created_at,
            auto_delete_at=auto_delete_at,
            tags=tags,
            options=options,
            insights_state=insights_state,
        )

        transcript_list_row.additional_properties = d
        return transcript_list_row

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
