from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.org_transcript import OrgTranscript


T = TypeVar("T", bound="OrgTranscriptsResponse")


@_attrs_define
class OrgTranscriptsResponse:
    """
    Attributes:
        transcripts (list[OrgTranscript]):
        next_cursor (None | str): An opaque token for the next page's cursor parameter, or null on the last page. This
            API refuses a cursor it did not mint.
    """

    transcripts: list[OrgTranscript]
    next_cursor: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        transcripts = []
        for transcripts_item_data in self.transcripts:
            transcripts_item = transcripts_item_data.to_dict()
            transcripts.append(transcripts_item)

        next_cursor: None | str
        next_cursor = self.next_cursor

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "transcripts": transcripts,
                "next_cursor": next_cursor,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.org_transcript import OrgTranscript  # noqa: PLC0415

        d = dict(src_dict)
        transcripts = []
        _transcripts = d.pop("transcripts")
        for transcripts_item_data in _transcripts:
            transcripts_item = OrgTranscript.from_dict(transcripts_item_data)

            transcripts.append(transcripts_item)

        def _parse_next_cursor(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        next_cursor = _parse_next_cursor(d.pop("next_cursor"))

        org_transcripts_response = cls(
            transcripts=transcripts,
            next_cursor=next_cursor,
        )

        org_transcripts_response.additional_properties = d
        return org_transcripts_response

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
