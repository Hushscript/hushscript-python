from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgInvoice")


@_attrs_define
class OrgInvoice:
    """
    Attributes:
        id (str):
        number (None | str):
        kind (str):
        sku (str):
        seconds (int):
        amount_cents (int):
        currency (str):
        payment_reference (str):
        status (str):
        po_number (None | str):
        issued_at (int):
        paid_at (int | None):
        created_at (int):
    """

    id: str
    number: None | str
    kind: str
    sku: str
    seconds: int
    amount_cents: int
    currency: str
    payment_reference: str
    status: str
    po_number: None | str
    issued_at: int
    paid_at: int | None
    created_at: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        number: None | str
        number = self.number

        kind = self.kind

        sku = self.sku

        seconds = self.seconds

        amount_cents = self.amount_cents

        currency = self.currency

        payment_reference = self.payment_reference

        status = self.status

        po_number: None | str
        po_number = self.po_number

        issued_at = self.issued_at

        paid_at: int | None
        paid_at = self.paid_at

        created_at = self.created_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "number": number,
                "kind": kind,
                "sku": sku,
                "seconds": seconds,
                "amount_cents": amount_cents,
                "currency": currency,
                "payment_reference": payment_reference,
                "status": status,
                "po_number": po_number,
                "issued_at": issued_at,
                "paid_at": paid_at,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        def _parse_number(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        number = _parse_number(d.pop("number"))

        kind = d.pop("kind")

        sku = d.pop("sku")

        seconds = d.pop("seconds")

        amount_cents = d.pop("amount_cents")

        currency = d.pop("currency")

        payment_reference = d.pop("payment_reference")

        status = d.pop("status")

        def _parse_po_number(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        po_number = _parse_po_number(d.pop("po_number"))

        issued_at = d.pop("issued_at")

        def _parse_paid_at(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        paid_at = _parse_paid_at(d.pop("paid_at"))

        created_at = d.pop("created_at")

        org_invoice = cls(
            id=id,
            number=number,
            kind=kind,
            sku=sku,
            seconds=seconds,
            amount_cents=amount_cents,
            currency=currency,
            payment_reference=payment_reference,
            status=status,
            po_number=po_number,
            issued_at=issued_at,
            paid_at=paid_at,
            created_at=created_at,
        )

        org_invoice.additional_properties = d
        return org_invoice

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
