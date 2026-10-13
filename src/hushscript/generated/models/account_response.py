from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.upload_limits import UploadLimits


T = TypeVar("T", bound="AccountResponse")


@_attrs_define
class AccountResponse:
    """
    Attributes:
        balance_seconds (int): Net balance in seconds: the raw balance minus any clawback debt. May be negative.
        held_seconds (int): Seconds currently committed to in-flight jobs and not yet settled.
        credits_expire_at (int | None): Unix seconds after which the balance expires without a completed transcription
            or purchase, or null if no expiry is currently armed.
        card_on_file (bool):
        data_region (str): The region this account's data lives in, e.g. us, eu, apac or oc.
        limits (UploadLimits): The caller's current upload admission limits, shared by every response that carries them.
    """

    balance_seconds: int
    held_seconds: int
    credits_expire_at: int | None
    card_on_file: bool
    data_region: str
    limits: UploadLimits
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        balance_seconds = self.balance_seconds

        held_seconds = self.held_seconds

        credits_expire_at: int | None
        credits_expire_at = self.credits_expire_at

        card_on_file = self.card_on_file

        data_region = self.data_region

        limits = self.limits.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "balance_seconds": balance_seconds,
                "held_seconds": held_seconds,
                "credits_expire_at": credits_expire_at,
                "card_on_file": card_on_file,
                "data_region": data_region,
                "limits": limits,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.upload_limits import UploadLimits  # noqa: PLC0415

        d = dict(src_dict)
        balance_seconds = d.pop("balance_seconds")

        held_seconds = d.pop("held_seconds")

        def _parse_credits_expire_at(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        credits_expire_at = _parse_credits_expire_at(d.pop("credits_expire_at"))

        card_on_file = d.pop("card_on_file")

        data_region = d.pop("data_region")

        limits = UploadLimits.from_dict(d.pop("limits"))

        account_response = cls(
            balance_seconds=balance_seconds,
            held_seconds=held_seconds,
            credits_expire_at=credits_expire_at,
            card_on_file=card_on_file,
            data_region=data_region,
            limits=limits,
        )

        account_response.additional_properties = d
        return account_response

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
