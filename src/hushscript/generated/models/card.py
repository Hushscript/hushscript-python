from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Card")


@_attrs_define
class Card:
    """
    Attributes:
        id (str): Use this value as quick_payment_method_id when it is is_default and fast_checkout_eligible. If
            default_id is null, naming any fast_checkout_eligible card here also makes it the new default.
        type_ (str):
        brand (str):
        last4 (str):
        exp_month (int):
        exp_year (int):
        email (None | str):
        is_default (bool):
        fast_checkout_eligible (bool): Whether this method may be charged off-session by buy_minutes.
    """

    id: str
    type_: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    email: None | str
    is_default: bool
    fast_checkout_eligible: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        type_ = self.type_

        brand = self.brand

        last4 = self.last4

        exp_month = self.exp_month

        exp_year = self.exp_year

        email: None | str
        email = self.email

        is_default = self.is_default

        fast_checkout_eligible = self.fast_checkout_eligible

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "type": type_,
                "brand": brand,
                "last4": last4,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "email": email,
                "is_default": is_default,
                "fast_checkout_eligible": fast_checkout_eligible,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        type_ = d.pop("type")

        brand = d.pop("brand")

        last4 = d.pop("last4")

        exp_month = d.pop("exp_month")

        exp_year = d.pop("exp_year")

        def _parse_email(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        email = _parse_email(d.pop("email"))

        is_default = d.pop("is_default")

        fast_checkout_eligible = d.pop("fast_checkout_eligible")

        card = cls(
            id=id,
            type_=type_,
            brand=brand,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            email=email,
            is_default=is_default,
            fast_checkout_eligible=fast_checkout_eligible,
        )

        card.additional_properties = d
        return card

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
