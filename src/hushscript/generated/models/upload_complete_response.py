from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="UploadCompleteResponse")


@_attrs_define
class UploadCompleteResponse:
    """
    Attributes:
        ok (bool):
        state (str): The job's state immediately after completion, e.g. queued, processing or done.
        verified_seconds (int | None): The probed exact duration, once verification has run; null while verification is
            still pending.
        balance_seconds (int): The account's net balance after the hold was reconciled to the verified duration.
        held_seconds (int):
    """

    ok: bool
    state: str
    verified_seconds: int | None
    balance_seconds: int
    held_seconds: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ok = self.ok

        state = self.state

        verified_seconds: int | None
        verified_seconds = self.verified_seconds

        balance_seconds = self.balance_seconds

        held_seconds = self.held_seconds

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "ok": ok,
                "state": state,
                "verified_seconds": verified_seconds,
                "balance_seconds": balance_seconds,
                "held_seconds": held_seconds,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        ok = d.pop("ok")

        state = d.pop("state")

        def _parse_verified_seconds(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        verified_seconds = _parse_verified_seconds(d.pop("verified_seconds"))

        balance_seconds = d.pop("balance_seconds")

        held_seconds = d.pop("held_seconds")

        upload_complete_response = cls(
            ok=ok,
            state=state,
            verified_seconds=verified_seconds,
            balance_seconds=balance_seconds,
            held_seconds=held_seconds,
        )

        upload_complete_response.additional_properties = d
        return upload_complete_response

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
