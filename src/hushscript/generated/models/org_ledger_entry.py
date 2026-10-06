from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgLedgerEntry")


@_attrs_define
class OrgLedgerEntry:
    """
    Attributes:
        id (int):
        delta_seconds (int):
        kind (str):
        job_id (None | str):
        invoice_id (None | str):
        actor_user_id (None | str):
        member_email (None | str):
        note (None | str):
        created_at (int):
    """

    id: int
    delta_seconds: int
    kind: str
    job_id: None | str
    invoice_id: None | str
    actor_user_id: None | str
    member_email: None | str
    note: None | str
    created_at: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        delta_seconds = self.delta_seconds

        kind = self.kind

        job_id: None | str
        job_id = self.job_id

        invoice_id: None | str
        invoice_id = self.invoice_id

        actor_user_id: None | str
        actor_user_id = self.actor_user_id

        member_email: None | str
        member_email = self.member_email

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
                "invoice_id": invoice_id,
                "actor_user_id": actor_user_id,
                "member_email": member_email,
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

        def _parse_invoice_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        invoice_id = _parse_invoice_id(d.pop("invoice_id"))

        def _parse_actor_user_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        actor_user_id = _parse_actor_user_id(d.pop("actor_user_id"))

        def _parse_member_email(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        member_email = _parse_member_email(d.pop("member_email"))

        def _parse_note(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        note = _parse_note(d.pop("note"))

        created_at = d.pop("created_at")

        org_ledger_entry = cls(
            id=id,
            delta_seconds=delta_seconds,
            kind=kind,
            job_id=job_id,
            invoice_id=invoice_id,
            actor_user_id=actor_user_id,
            member_email=member_email,
            note=note,
            created_at=created_at,
        )

        org_ledger_entry.additional_properties = d
        return org_ledger_entry

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
