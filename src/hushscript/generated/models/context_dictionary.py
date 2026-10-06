from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.dictionary_entry import DictionaryEntry


T = TypeVar("T", bound="ContextDictionary")


@_attrs_define
class ContextDictionary:
    """
    Attributes:
        id (str):
        name (str):
        description (str): Free-text description. Empty when unset; never null.
        language_code (str): The language this applies to: all, or one of the supported source language codes. Never
            empty and never null: unset is stored as all.
        entries (list[DictionaryEntry]):
        terms (list[str]): The flat recognition terms this dictionary compiles into. Derived from entries when entries
            exist (every canonical spelling and its variants, deduplicated); otherwise the legacy flat list stored before
            entries existed.
        is_default (bool): Whether this dictionary is applied to an upload that selects none explicitly. At most one
            dictionary is the default.
        created_at (int):
        updated_at (int):
    """

    id: str
    name: str
    description: str
    language_code: str
    entries: list[DictionaryEntry]
    terms: list[str]
    is_default: bool
    created_at: int
    updated_at: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        description = self.description

        language_code = self.language_code

        entries = []
        for entries_item_data in self.entries:
            entries_item = entries_item_data.to_dict()
            entries.append(entries_item)

        terms = self.terms

        is_default = self.is_default

        created_at = self.created_at

        updated_at = self.updated_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "description": description,
                "language_code": language_code,
                "entries": entries,
                "terms": terms,
                "is_default": is_default,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.dictionary_entry import DictionaryEntry  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        description = d.pop("description")

        language_code = d.pop("language_code")

        entries = []
        _entries = d.pop("entries")
        for entries_item_data in _entries:
            entries_item = DictionaryEntry.from_dict(entries_item_data)

            entries.append(entries_item)

        terms = cast(list[str], d.pop("terms"))

        is_default = d.pop("is_default")

        created_at = d.pop("created_at")

        updated_at = d.pop("updated_at")

        context_dictionary = cls(
            id=id,
            name=name,
            description=description,
            language_code=language_code,
            entries=entries,
            terms=terms,
            is_default=is_default,
            created_at=created_at,
            updated_at=updated_at,
        )

        context_dictionary.additional_properties = d
        return context_dictionary

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
