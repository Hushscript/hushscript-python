from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.deleted_transcript_cause import (
    DeletedTranscriptCause,
    check_deleted_transcript_cause,
)

if TYPE_CHECKING:
    from ..models.deleted_transcript_receipt_type_0 import DeletedTranscriptReceiptType0


T = TypeVar("T", bound="DeletedTranscript")


@_attrs_define
class DeletedTranscript:
    """
    Attributes:
        id (str):
        title (str):
        duration_seconds (int):
        created_at (int): When the transcript was originally uploaded, Unix seconds. This is the key the list is ordered
            and paged on.
        deleted_at (int):
        cause (DeletedTranscriptCause): Which deletion path removed the transcript: an explicit delete (manual), the
            transcript's own auto_delete_at retention date (scheduled), the dormant-account purge (dormant), or the global
            retention sweep (expired).
        receipt (DeletedTranscriptReceiptType0 | None): The receipt recorded when the transcript was deleted, kept so
            the deletion stays evidenced after the content itself is gone. Null when the stored receipt could not be read
            back.
    """

    id: str
    title: str
    duration_seconds: int
    created_at: int
    deleted_at: int
    cause: DeletedTranscriptCause
    receipt: DeletedTranscriptReceiptType0 | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.deleted_transcript_receipt_type_0 import (
            DeletedTranscriptReceiptType0,  # noqa: PLC0415
        )

        id = self.id

        title = self.title

        duration_seconds = self.duration_seconds

        created_at = self.created_at

        deleted_at = self.deleted_at

        cause: str = self.cause

        receipt: dict[str, Any] | None
        if isinstance(self.receipt, DeletedTranscriptReceiptType0):
            receipt = self.receipt.to_dict()
        else:
            receipt = self.receipt

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "title": title,
                "duration_seconds": duration_seconds,
                "created_at": created_at,
                "deleted_at": deleted_at,
                "cause": cause,
                "receipt": receipt,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.deleted_transcript_receipt_type_0 import (
            DeletedTranscriptReceiptType0,  # noqa: PLC0415
        )

        d = dict(src_dict)
        id = d.pop("id")

        title = d.pop("title")

        duration_seconds = d.pop("duration_seconds")

        created_at = d.pop("created_at")

        deleted_at = d.pop("deleted_at")

        cause = check_deleted_transcript_cause(d.pop("cause"))

        def _parse_receipt(data: object) -> DeletedTranscriptReceiptType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                receipt_type_0 = DeletedTranscriptReceiptType0.from_dict(data)

                return receipt_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(DeletedTranscriptReceiptType0 | None, data)

        receipt = _parse_receipt(d.pop("receipt"))

        deleted_transcript = cls(
            id=id,
            title=title,
            duration_seconds=duration_seconds,
            created_at=created_at,
            deleted_at=deleted_at,
            cause=cause,
            receipt=receipt,
        )

        deleted_transcript.additional_properties = d
        return deleted_transcript

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
