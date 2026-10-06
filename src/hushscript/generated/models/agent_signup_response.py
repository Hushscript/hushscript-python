from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AgentSignupResponse")


@_attrs_define
class AgentSignupResponse:
    """
    Attributes:
        signup_id (str): Region-prefixed (hsr1:<region>:<id>), e.g. hsr1:eu:4c3a1f9e7b2d4e6f8a0c1b2d3e4f5061. Present it
            back verbatim as the path segment when claiming the account. A dry_run response's signup_id is prefixed dry_
            instead and can never be claimed.
        claim_secret (str): Returned exactly once. Only its hash is stored; there is no way to recover it later.
        checkout_url (str): Open this URL in a browser you control to complete the hosted Checkout page.
        pack (str):
        amount (int): Charge amount in the currency's minor unit.
        currency (str):
        expires_at (int): Unix timestamp after which the Session stops accepting a card.
    """

    signup_id: str
    claim_secret: str
    checkout_url: str
    pack: str
    amount: int
    currency: str
    expires_at: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        signup_id = self.signup_id

        claim_secret = self.claim_secret

        checkout_url = self.checkout_url

        pack = self.pack

        amount = self.amount

        currency = self.currency

        expires_at = self.expires_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "signup_id": signup_id,
                "claim_secret": claim_secret,
                "checkout_url": checkout_url,
                "pack": pack,
                "amount": amount,
                "currency": currency,
                "expires_at": expires_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        signup_id = d.pop("signup_id")

        claim_secret = d.pop("claim_secret")

        checkout_url = d.pop("checkout_url")

        pack = d.pop("pack")

        amount = d.pop("amount")

        currency = d.pop("currency")

        expires_at = d.pop("expires_at")

        agent_signup_response = cls(
            signup_id=signup_id,
            claim_secret=claim_secret,
            checkout_url=checkout_url,
            pack=pack,
            amount=amount,
            currency=currency,
            expires_at=expires_at,
        )

        agent_signup_response.additional_properties = d
        return agent_signup_response

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
