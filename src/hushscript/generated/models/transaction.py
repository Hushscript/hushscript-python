from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Transaction")


@_attrs_define
class Transaction:
    """
    Attributes:
        id (int): This row's own id.
        seconds (int):
        amount_cents (int):
        amount_refunded_cents (int):
        currency (str):
        status (str):
        created_at (int):
        payment_method_type (None | str):
        payment_method_brand (None | str):
        payment_method_last4 (None | str):
        receipt_number (None | str): The public receipt reference, e.g. HS-20260101-abcdef0123456789-1.
        initiated_via (None | str):
    """

    id: int
    seconds: int
    amount_cents: int
    amount_refunded_cents: int
    currency: str
    status: str
    created_at: int
    payment_method_type: None | str
    payment_method_brand: None | str
    payment_method_last4: None | str
    receipt_number: None | str
    initiated_via: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        seconds = self.seconds

        amount_cents = self.amount_cents

        amount_refunded_cents = self.amount_refunded_cents

        currency = self.currency

        status = self.status

        created_at = self.created_at

        payment_method_type: None | str
        payment_method_type = self.payment_method_type

        payment_method_brand: None | str
        payment_method_brand = self.payment_method_brand

        payment_method_last4: None | str
        payment_method_last4 = self.payment_method_last4

        receipt_number: None | str
        receipt_number = self.receipt_number

        initiated_via: None | str
        initiated_via = self.initiated_via

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "seconds": seconds,
                "amount_cents": amount_cents,
                "amount_refunded_cents": amount_refunded_cents,
                "currency": currency,
                "status": status,
                "created_at": created_at,
                "payment_method_type": payment_method_type,
                "payment_method_brand": payment_method_brand,
                "payment_method_last4": payment_method_last4,
                "receipt_number": receipt_number,
                "initiated_via": initiated_via,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        seconds = d.pop("seconds")

        amount_cents = d.pop("amount_cents")

        amount_refunded_cents = d.pop("amount_refunded_cents")

        currency = d.pop("currency")

        status = d.pop("status")

        created_at = d.pop("created_at")

        def _parse_payment_method_type(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        payment_method_type = _parse_payment_method_type(d.pop("payment_method_type"))

        def _parse_payment_method_brand(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        payment_method_brand = _parse_payment_method_brand(
            d.pop("payment_method_brand")
        )

        def _parse_payment_method_last4(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        payment_method_last4 = _parse_payment_method_last4(
            d.pop("payment_method_last4")
        )

        def _parse_receipt_number(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        receipt_number = _parse_receipt_number(d.pop("receipt_number"))

        def _parse_initiated_via(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        initiated_via = _parse_initiated_via(d.pop("initiated_via"))

        transaction = cls(
            id=id,
            seconds=seconds,
            amount_cents=amount_cents,
            amount_refunded_cents=amount_refunded_cents,
            currency=currency,
            status=status,
            created_at=created_at,
            payment_method_type=payment_method_type,
            payment_method_brand=payment_method_brand,
            payment_method_last4=payment_method_last4,
            receipt_number=receipt_number,
            initiated_via=initiated_via,
        )

        transaction.additional_properties = d
        return transaction

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
