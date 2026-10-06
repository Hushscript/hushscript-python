from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.org_invoice import OrgInvoice


T = TypeVar("T", bound="OrgInvoicesResponse")


@_attrs_define
class OrgInvoicesResponse:
    """
    Attributes:
        invoices (list[OrgInvoice]):
        next_cursor (None | str): An opaque token for the next page's cursor parameter, or null on the last page. This
            API refuses a cursor it did not mint.
    """

    invoices: list[OrgInvoice]
    next_cursor: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        invoices = []
        for invoices_item_data in self.invoices:
            invoices_item = invoices_item_data.to_dict()
            invoices.append(invoices_item)

        next_cursor: None | str
        next_cursor = self.next_cursor

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "invoices": invoices,
                "next_cursor": next_cursor,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.org_invoice import OrgInvoice  # noqa: PLC0415

        d = dict(src_dict)
        invoices = []
        _invoices = d.pop("invoices")
        for invoices_item_data in _invoices:
            invoices_item = OrgInvoice.from_dict(invoices_item_data)

            invoices.append(invoices_item)

        def _parse_next_cursor(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        next_cursor = _parse_next_cursor(d.pop("next_cursor"))

        org_invoices_response = cls(
            invoices=invoices,
            next_cursor=next_cursor,
        )

        org_invoices_response.additional_properties = d
        return org_invoices_response

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
