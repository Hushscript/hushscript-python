from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.card import Card


T = TypeVar("T", bound="CardsResponse")


@_attrs_define
class CardsResponse:
    """
    Attributes:
        default_id (None | str):
        methods (list[Card]):
    """

    default_id: None | str
    methods: list[Card]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        default_id: None | str
        default_id = self.default_id

        methods = []
        for methods_item_data in self.methods:
            methods_item = methods_item_data.to_dict()
            methods.append(methods_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "default_id": default_id,
                "methods": methods,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.card import Card  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_default_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        default_id = _parse_default_id(d.pop("default_id"))

        methods = []
        _methods = d.pop("methods")
        for methods_item_data in _methods:
            methods_item = Card.from_dict(methods_item_data)

            methods.append(methods_item)

        cards_response = cls(
            default_id=default_id,
            methods=methods,
        )

        cards_response.additional_properties = d
        return cards_response

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
