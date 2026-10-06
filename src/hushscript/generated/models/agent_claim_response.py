from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="AgentClaimResponse")


@_attrs_define
class AgentClaimResponse:
    """
    Attributes:
        user_id (str): The account created by this claim. There is no login path for it; authenticate with pat instead.
        pat (str): Returned exactly once. Only its hash is stored; there is no way to recover it later.
        scopes (list[str]): The scopes carried by pat.
        balance_seconds (int): The account's balance immediately after the pack this signup paid for was granted.
    """

    user_id: str
    pat: str
    scopes: list[str]
    balance_seconds: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        user_id = self.user_id

        pat = self.pat

        scopes = self.scopes

        balance_seconds = self.balance_seconds

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "user_id": user_id,
                "pat": pat,
                "scopes": scopes,
                "balance_seconds": balance_seconds,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        user_id = d.pop("user_id")

        pat = d.pop("pat")

        scopes = cast(list[str], d.pop("scopes"))

        balance_seconds = d.pop("balance_seconds")

        agent_claim_response = cls(
            user_id=user_id,
            pat=pat,
            scopes=scopes,
            balance_seconds=balance_seconds,
        )

        agent_claim_response.additional_properties = d
        return agent_claim_response

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
