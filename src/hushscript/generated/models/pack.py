from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="Pack")


@_attrs_define
class Pack:
    """
    Attributes:
        id (str):
        amount (int): The price in minor units of currency, already localized for the account's country.
        currency (str):
        seconds (int):
        referral_bonus_seconds (int): Extra seconds this purchase would add from an available referral buyer bonus. Zero
            when none is available.
        available (bool | Unset): Whether the caller's account may buy this pack right now. Present for agent accounts
            only: an agent's pack tier gates the larger packs until enough prior payments have settled past the dispute
            window. Absent on every human caller's response, whose packs are all always available.
    """

    id: str
    amount: int
    currency: str
    seconds: int
    referral_bonus_seconds: int
    available: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        amount = self.amount

        currency = self.currency

        seconds = self.seconds

        referral_bonus_seconds = self.referral_bonus_seconds

        available = self.available

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "amount": amount,
                "currency": currency,
                "seconds": seconds,
                "referral_bonus_seconds": referral_bonus_seconds,
            }
        )
        if available is not UNSET:
            field_dict["available"] = available

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        amount = d.pop("amount")

        currency = d.pop("currency")

        seconds = d.pop("seconds")

        referral_bonus_seconds = d.pop("referral_bonus_seconds")

        available = d.pop("available", UNSET)

        pack = cls(
            id=id,
            amount=amount,
            currency=currency,
            seconds=seconds,
            referral_bonus_seconds=referral_bonus_seconds,
            available=available,
        )

        pack.additional_properties = d
        return pack

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
