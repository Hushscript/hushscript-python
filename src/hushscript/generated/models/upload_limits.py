from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="UploadLimits")


@_attrs_define
class UploadLimits:
    """The caller's current upload admission limits, shared by every response that carries them.

    Attributes:
        max_daily_seconds (int): The account's daily transcription-minutes cap, in seconds.
        max_active_jobs (int): The maximum number of concurrent pipeline jobs this account may have in flight.
        active_jobs (int): How many pipeline jobs are currently in flight.
        used_today_seconds (int): Billable seconds already used today, in the account's own rolling day.
    """

    max_daily_seconds: int
    max_active_jobs: int
    active_jobs: int
    used_today_seconds: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        max_daily_seconds = self.max_daily_seconds

        max_active_jobs = self.max_active_jobs

        active_jobs = self.active_jobs

        used_today_seconds = self.used_today_seconds

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "max_daily_seconds": max_daily_seconds,
                "max_active_jobs": max_active_jobs,
                "active_jobs": active_jobs,
                "used_today_seconds": used_today_seconds,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        max_daily_seconds = d.pop("max_daily_seconds")

        max_active_jobs = d.pop("max_active_jobs")

        active_jobs = d.pop("active_jobs")

        used_today_seconds = d.pop("used_today_seconds")

        upload_limits = cls(
            max_daily_seconds=max_daily_seconds,
            max_active_jobs=max_active_jobs,
            active_jobs=active_jobs,
            used_today_seconds=used_today_seconds,
        )

        upload_limits.additional_properties = d
        return upload_limits

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
