from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CreditLedgerEntry")


@_attrs_define
class CreditLedgerEntry:
    """
    Attributes:
        id (int):
        delta_seconds (int):
        kind (str):
        job_id (None | str):
        note (None | str):
        created_at (int):
    """

    id: int
    delta_seconds: int
    kind: str
    job_id: None | str
    note: None | str
    created_at: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        delta_seconds = self.delta_seconds

        kind = self.kind

        job_id: None | str
        job_id = self.job_id

        note: None | str
        note = self.note

        created_at = self.created_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "delta_seconds": delta_seconds,
                "kind": kind,
                "job_id": job_id,
                "note": note,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        delta_seconds = d.pop("delta_seconds")

        kind = d.pop("kind")

        def _parse_job_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        job_id = _parse_job_id(d.pop("job_id"))

        def _parse_note(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        note = _parse_note(d.pop("note"))

        created_at = d.pop("created_at")

        credit_ledger_entry = cls(
            id=id,
            delta_seconds=delta_seconds,
            kind=kind,
            job_id=job_id,
            note=note,
            created_at=created_at,
        )

        credit_ledger_entry.additional_properties = d
        return credit_ledger_entry

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
