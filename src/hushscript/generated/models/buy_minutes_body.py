from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="BuyMinutesBody")


@_attrs_define
class BuyMinutesBody:
    """
    Attributes:
        pack (str): The id of a pack from list_packs.
        idempotency_key (str): A client-minted key preventing a retried request from charging twice.
        quick_payment_method_id (str): The id of a card from list_saved_cards, required on this API.
        policy_ack (bool | Unset): Client attestation that the no-refund, instant-delivery notice was shown before this
            call. Optional; absent is treated as false.
    """

    pack: str
    idempotency_key: str
    quick_payment_method_id: str
    policy_ack: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        pack = self.pack

        idempotency_key = self.idempotency_key

        quick_payment_method_id = self.quick_payment_method_id

        policy_ack = self.policy_ack

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "pack": pack,
                "idempotency_key": idempotency_key,
                "quick_payment_method_id": quick_payment_method_id,
            }
        )
        if policy_ack is not UNSET:
            field_dict["policy_ack"] = policy_ack

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        pack = d.pop("pack")

        idempotency_key = d.pop("idempotency_key")

        quick_payment_method_id = d.pop("quick_payment_method_id")

        policy_ack = d.pop("policy_ack", UNSET)

        buy_minutes_body = cls(
            pack=pack,
            idempotency_key=idempotency_key,
            quick_payment_method_id=quick_payment_method_id,
            policy_ack=policy_ack,
        )

        buy_minutes_body.additional_properties = d
        return buy_minutes_body

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
