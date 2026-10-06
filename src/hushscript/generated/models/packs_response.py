from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.pack import Pack


T = TypeVar("T", bound="PacksResponse")


@_attrs_define
class PacksResponse:
    """
    Attributes:
        packs (list[Pack]):
    """

    packs: list[Pack]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        packs = []
        for packs_item_data in self.packs:
            packs_item = packs_item_data.to_dict()
            packs.append(packs_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "packs": packs,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.pack import Pack  # noqa: PLC0415

        d = dict(src_dict)
        packs = []
        _packs = d.pop("packs")
        for packs_item_data in _packs:
            packs_item = Pack.from_dict(packs_item_data)

            packs.append(packs_item)

        packs_response = cls(
            packs=packs,
        )

        packs_response.additional_properties = d
        return packs_response

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
