from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.deleted_transcript_receipt_type_0_items_item import (
        DeletedTranscriptReceiptType0ItemsItem,
    )


T = TypeVar("T", bound="DeletedTranscriptReceiptType0")


@_attrs_define
class DeletedTranscriptReceiptType0:
    """The receipt recorded when the transcript was deleted, kept so the deletion stays evidenced after the content itself
    is gone. Null when the stored receipt could not be read back.

        Attributes:
            type_ (str):
            version (int):
            created_at (str): UTC timestamp, seconds precision.
            items (list[DeletedTranscriptReceiptType0ItemsItem]):
    """

    type_: str
    version: int
    created_at: str
    items: list[DeletedTranscriptReceiptType0ItemsItem]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_

        version = self.version

        created_at = self.created_at

        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "version": version,
                "created_at": created_at,
                "items": items,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.deleted_transcript_receipt_type_0_items_item import (
            DeletedTranscriptReceiptType0ItemsItem,  # noqa: PLC0415
        )

        d = dict(src_dict)
        type_ = d.pop("type")

        version = d.pop("version")

        created_at = d.pop("created_at")

        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = DeletedTranscriptReceiptType0ItemsItem.from_dict(
                items_item_data
            )

            items.append(items_item)

        deleted_transcript_receipt_type_0 = cls(
            type_=type_,
            version=version,
            created_at=created_at,
            items=items,
        )

        deleted_transcript_receipt_type_0.additional_properties = d
        return deleted_transcript_receipt_type_0

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
