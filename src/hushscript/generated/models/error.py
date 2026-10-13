from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.error_details import ErrorDetails
    from ..models.upload_limits import UploadLimits


T = TypeVar("T", bound="Error")


@_attrs_define
class Error:
    """The frozen /v1 error body. error and code are always present together; the remaining keys are optional detail this
    API includes only when the specific error carries them, and they are omitted rather than emitted as null when
    absent.

        Attributes:
            error (str): The error's slug. See x-error-catalog for the full list.
            code (int): The error's stable numeric code. See x-error-catalog. Never reused or renumbered.
            needed_seconds (int | Unset): Seconds the failed action needed. Present on a balance-shortfall error.
            balance_seconds (int | Unset): The account's personal balance in seconds. Present on a personal balance-
                shortfall error.
            held_seconds (int | Unset): Seconds already committed to other in-flight jobs. Present alongside
                balance_seconds.
            org_balance_seconds (int | Unset): The organization's shared pool balance in seconds. Present on an org-funded
                balance-shortfall error instead of balance_seconds.
            limits (UploadLimits | Unset): The caller's current upload admission limits, shared by every response that
                carries them.
            details (ErrorDetails | Unset): Structured recovery detail for an error that is not a plain balance shortfall.
                Present on agent_pack_locked and agent_purchase_capped.
    """

    error: str
    code: int
    needed_seconds: int | Unset = UNSET
    balance_seconds: int | Unset = UNSET
    held_seconds: int | Unset = UNSET
    org_balance_seconds: int | Unset = UNSET
    limits: UploadLimits | Unset = UNSET
    details: ErrorDetails | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        error = self.error

        code = self.code

        needed_seconds = self.needed_seconds

        balance_seconds = self.balance_seconds

        held_seconds = self.held_seconds

        org_balance_seconds = self.org_balance_seconds

        limits: dict[str, Any] | Unset = UNSET
        if not isinstance(self.limits, Unset):
            limits = self.limits.to_dict()

        details: dict[str, Any] | Unset = UNSET
        if not isinstance(self.details, Unset):
            details = self.details.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "error": error,
                "code": code,
            }
        )
        if needed_seconds is not UNSET:
            field_dict["needed_seconds"] = needed_seconds
        if balance_seconds is not UNSET:
            field_dict["balance_seconds"] = balance_seconds
        if held_seconds is not UNSET:
            field_dict["held_seconds"] = held_seconds
        if org_balance_seconds is not UNSET:
            field_dict["org_balance_seconds"] = org_balance_seconds
        if limits is not UNSET:
            field_dict["limits"] = limits
        if details is not UNSET:
            field_dict["details"] = details

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.error_details import ErrorDetails  # noqa: PLC0415
        from ..models.upload_limits import UploadLimits  # noqa: PLC0415

        d = dict(src_dict)
        error = d.pop("error")

        code = d.pop("code")

        needed_seconds = d.pop("needed_seconds", UNSET)

        balance_seconds = d.pop("balance_seconds", UNSET)

        held_seconds = d.pop("held_seconds", UNSET)

        org_balance_seconds = d.pop("org_balance_seconds", UNSET)

        _limits = d.pop("limits", UNSET)
        limits: UploadLimits | Unset
        if isinstance(_limits, Unset):
            limits = UNSET
        else:
            limits = UploadLimits.from_dict(_limits)

        _details = d.pop("details", UNSET)
        details: ErrorDetails | Unset
        if isinstance(_details, Unset):
            details = UNSET
        else:
            details = ErrorDetails.from_dict(_details)

        error = cls(
            error=error,
            code=code,
            needed_seconds=needed_seconds,
            balance_seconds=balance_seconds,
            held_seconds=held_seconds,
            org_balance_seconds=org_balance_seconds,
            limits=limits,
            details=details,
        )

        error.additional_properties = d
        return error

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
