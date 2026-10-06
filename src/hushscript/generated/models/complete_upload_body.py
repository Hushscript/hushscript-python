from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.complete_upload_body_parts_type_0_item import (
        CompleteUploadBodyPartsType0Item,
    )


T = TypeVar("T", bound="CompleteUploadBody")


@_attrs_define
class CompleteUploadBody:
    """
    Attributes:
        parts (list[CompleteUploadBodyPartsType0Item] | None | Unset): The part number and ETag of every part a direct-
            to-R2 client uploaded. Omit entirely for a worker-uploaded job.
    """

    parts: list[CompleteUploadBodyPartsType0Item] | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        parts: list[dict[str, Any]] | None | Unset
        if isinstance(self.parts, Unset):
            parts = UNSET
        elif isinstance(self.parts, list):
            parts = []
            for parts_type_0_item_data in self.parts:
                parts_type_0_item = parts_type_0_item_data.to_dict()
                parts.append(parts_type_0_item)

        else:
            parts = self.parts

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if parts is not UNSET:
            field_dict["parts"] = parts

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.complete_upload_body_parts_type_0_item import (
            CompleteUploadBodyPartsType0Item,  # noqa: PLC0415
        )

        d = dict(src_dict)

        def _parse_parts(
            data: object,
        ) -> list[CompleteUploadBodyPartsType0Item] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                parts_type_0 = []
                _parts_type_0 = data
                for parts_type_0_item_data in _parts_type_0:
                    parts_type_0_item = CompleteUploadBodyPartsType0Item.from_dict(
                        parts_type_0_item_data
                    )

                    parts_type_0.append(parts_type_0_item)

                return parts_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[CompleteUploadBodyPartsType0Item] | None | Unset, data)

        parts = _parse_parts(d.pop("parts", UNSET))

        complete_upload_body = cls(
            parts=parts,
        )

        complete_upload_body.additional_properties = d
        return complete_upload_body

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
