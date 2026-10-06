from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.org_matter import OrgMatter


T = TypeVar("T", bound="OrgMattersResponse")


@_attrs_define
class OrgMattersResponse:
    """
    Attributes:
        matters (list[OrgMatter]):
    """

    matters: list[OrgMatter]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        matters = []
        for matters_item_data in self.matters:
            matters_item = matters_item_data.to_dict()
            matters.append(matters_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "matters": matters,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.org_matter import OrgMatter  # noqa: PLC0415

        d = dict(src_dict)
        matters = []
        _matters = d.pop("matters")
        for matters_item_data in _matters:
            matters_item = OrgMatter.from_dict(matters_item_data)

            matters.append(matters_item)

        org_matters_response = cls(
            matters=matters,
        )

        org_matters_response.additional_properties = d
        return org_matters_response

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
