from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AgentCredentialsRotateResponse")


@_attrs_define
class AgentCredentialsRotateResponse:
    """
    Attributes:
        pat (str): The successor token, returned exactly once. Only its hash is stored; there is no way to recover it
            later. The predecessor that authenticated this request stops working immediately.
        pat_id (str): The successor's id.
        scopes (list[str]): The scopes carried by pat, identical to the predecessor's.
        expires_at (int | None | Unset): The successor's expiry policy, carried over from the predecessor unchanged.
            Null when the predecessor never expired.
    """

    pat: str
    pat_id: str
    scopes: list[str]
    expires_at: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        pat = self.pat

        pat_id = self.pat_id

        scopes = self.scopes

        expires_at: int | None | Unset
        if isinstance(self.expires_at, Unset):
            expires_at = UNSET
        else:
            expires_at = self.expires_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "pat": pat,
                "pat_id": pat_id,
                "scopes": scopes,
            }
        )
        if expires_at is not UNSET:
            field_dict["expires_at"] = expires_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        pat = d.pop("pat")

        pat_id = d.pop("pat_id")

        scopes = cast(list[str], d.pop("scopes"))

        def _parse_expires_at(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        expires_at = _parse_expires_at(d.pop("expires_at", UNSET))

        agent_credentials_rotate_response = cls(
            pat=pat,
            pat_id=pat_id,
            scopes=scopes,
            expires_at=expires_at,
        )

        agent_credentials_rotate_response.additional_properties = d
        return agent_credentials_rotate_response

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
