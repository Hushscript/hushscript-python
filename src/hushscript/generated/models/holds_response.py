from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.active_hold import ActiveHold


T = TypeVar("T", bound="HoldsResponse")


@_attrs_define
class HoldsResponse:
    """
    Attributes:
        holds (list[ActiveHold]):
        next_cursor (None | str): An opaque token for the next page's cursor parameter, or null on the last page. This
            API refuses a cursor it did not mint.
    """

    holds: list[ActiveHold]
    next_cursor: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        holds = []
        for holds_item_data in self.holds:
            holds_item = holds_item_data.to_dict()
            holds.append(holds_item)

        next_cursor: None | str
        next_cursor = self.next_cursor

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "holds": holds,
                "next_cursor": next_cursor,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.active_hold import ActiveHold  # noqa: PLC0415

        d = dict(src_dict)
        holds = []
        _holds = d.pop("holds")
        for holds_item_data in _holds:
            holds_item = ActiveHold.from_dict(holds_item_data)

            holds.append(holds_item)

        def _parse_next_cursor(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        next_cursor = _parse_next_cursor(d.pop("next_cursor"))

        holds_response = cls(
            holds=holds,
            next_cursor=next_cursor,
        )

        holds_response.additional_properties = d
        return holds_response

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
