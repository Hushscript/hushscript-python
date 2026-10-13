from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.dictionary_entry_category import (
    DictionaryEntryCategory,
    check_dictionary_entry_category,
)

T = TypeVar("T", bound="DictionaryEntry")


@_attrs_define
class DictionaryEntry:
    """
    Attributes:
        id (str):
        canonical (str): The spelling the transcript should use.
        variants (list[str]): Alternative spellings that should be normalized to the canonical form.
        category (DictionaryEntryCategory): What kind of term this is. Never empty and never null: an entry saved
            without a category is stored as other.
        note (str): Free-text note about the entry. Empty when unset; never null.
        case_sensitive (bool):
        created_at (int):
        updated_at (int):
    """

    id: str
    canonical: str
    variants: list[str]
    category: DictionaryEntryCategory
    note: str
    case_sensitive: bool
    created_at: int
    updated_at: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        canonical = self.canonical

        variants = self.variants

        category: str = self.category

        note = self.note

        case_sensitive = self.case_sensitive

        created_at = self.created_at

        updated_at = self.updated_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "canonical": canonical,
                "variants": variants,
                "category": category,
                "note": note,
                "case_sensitive": case_sensitive,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        canonical = d.pop("canonical")

        variants = cast(list[str], d.pop("variants"))

        category = check_dictionary_entry_category(d.pop("category"))

        note = d.pop("note")

        case_sensitive = d.pop("case_sensitive")

        created_at = d.pop("created_at")

        updated_at = d.pop("updated_at")

        dictionary_entry = cls(
            id=id,
            canonical=canonical,
            variants=variants,
            category=category,
            note=note,
            case_sensitive=case_sensitive,
            created_at=created_at,
            updated_at=updated_at,
        )

        dictionary_entry.additional_properties = d
        return dictionary_entry

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
