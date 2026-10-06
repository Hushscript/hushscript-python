from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.presigned_part_url import PresignedPartUrl


T = TypeVar("T", bound="GetUploadPartUrlsResponse200Type0")


@_attrs_define
class GetUploadPartUrlsResponse200Type0:
    """One page of presigned direct-to-R2 PUT URLs, or null when direct-to-R2 uploads are not available for this job and
    parts must be sent to upload_part instead.

        Attributes:
            part_size_bytes (int): The byte size of every part except the last.
            total_parts (int): The total number of parts this upload is split into.
            part_urls (list[PresignedPartUrl]): Presigned URLs for this page's parts, starting at the requested (or first)
                part number.
            next_part_number (int | None): The next part number not covered by this page, or null once every part has a URL.
    """

    part_size_bytes: int
    total_parts: int
    part_urls: list[PresignedPartUrl]
    next_part_number: int | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        part_size_bytes = self.part_size_bytes

        total_parts = self.total_parts

        part_urls = []
        for part_urls_item_data in self.part_urls:
            part_urls_item = part_urls_item_data.to_dict()
            part_urls.append(part_urls_item)

        next_part_number: int | None
        next_part_number = self.next_part_number

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "part_size_bytes": part_size_bytes,
                "total_parts": total_parts,
                "part_urls": part_urls,
                "next_part_number": next_part_number,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.presigned_part_url import PresignedPartUrl  # noqa: PLC0415

        d = dict(src_dict)
        part_size_bytes = d.pop("part_size_bytes")

        total_parts = d.pop("total_parts")

        part_urls = []
        _part_urls = d.pop("part_urls")
        for part_urls_item_data in _part_urls:
            part_urls_item = PresignedPartUrl.from_dict(part_urls_item_data)

            part_urls.append(part_urls_item)

        def _parse_next_part_number(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        next_part_number = _parse_next_part_number(d.pop("next_part_number"))

        get_upload_part_urls_response_200_type_0 = cls(
            part_size_bytes=part_size_bytes,
            total_parts=total_parts,
            part_urls=part_urls,
            next_part_number=next_part_number,
        )

        get_upload_part_urls_response_200_type_0.additional_properties = d
        return get_upload_part_urls_response_200_type_0

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
