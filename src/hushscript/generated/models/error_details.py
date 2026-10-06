from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ErrorDetails")


@_attrs_define
class ErrorDetails:
    """Structured recovery detail for an error that is not a plain balance shortfall. Present on agent_pack_locked and
    agent_purchase_capped.

        Attributes:
            allowed_packs (list[str] | Unset): Pack ids the agent account may buy right now. Present on agent_pack_locked;
                retry with one of these.
            limit (int | Unset): The per-credential purchase cap for the rolling window. Present on agent_purchase_capped.
            window_seconds (int | Unset): The length of the rolling window in seconds. Present on agent_purchase_capped.
            retry_after_seconds (int | Unset): Seconds until the oldest purchase counted toward the cap leaves the window.
                Present on agent_purchase_capped; matches the Retry-After header.
    """

    allowed_packs: list[str] | Unset = UNSET
    limit: int | Unset = UNSET
    window_seconds: int | Unset = UNSET
    retry_after_seconds: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        allowed_packs: list[str] | Unset = UNSET
        if not isinstance(self.allowed_packs, Unset):
            allowed_packs = self.allowed_packs

        limit = self.limit

        window_seconds = self.window_seconds

        retry_after_seconds = self.retry_after_seconds

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if allowed_packs is not UNSET:
            field_dict["allowed_packs"] = allowed_packs
        if limit is not UNSET:
            field_dict["limit"] = limit
        if window_seconds is not UNSET:
            field_dict["window_seconds"] = window_seconds
        if retry_after_seconds is not UNSET:
            field_dict["retry_after_seconds"] = retry_after_seconds

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        allowed_packs = cast(list[str], d.pop("allowed_packs", UNSET))

        limit = d.pop("limit", UNSET)

        window_seconds = d.pop("window_seconds", UNSET)

        retry_after_seconds = d.pop("retry_after_seconds", UNSET)

        error_details = cls(
            allowed_packs=allowed_packs,
            limit=limit,
            window_seconds=window_seconds,
            retry_after_seconds=retry_after_seconds,
        )

        error_details.additional_properties = d
        return error_details

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
