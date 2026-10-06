from typing import Literal

DictionaryEntryCategory = Literal[
    "abbreviation",
    "acronym",
    "legal_term",
    "medical_term",
    "organization",
    "other",
    "person_name",
    "place",
    "preferred_spelling",
    "product",
    "technical_term",
]

DICTIONARY_ENTRY_CATEGORY_VALUES: set[DictionaryEntryCategory] = {
    "abbreviation",
    "acronym",
    "legal_term",
    "medical_term",
    "organization",
    "other",
    "person_name",
    "place",
    "preferred_spelling",
    "product",
    "technical_term",
}


def check_dictionary_entry_category(value: str) -> DictionaryEntryCategory:
    if value in DICTIONARY_ENTRY_CATEGORY_VALUES:
        return value
    raise TypeError(
        f"Unexpected value {value!r}. Expected one of {DICTIONARY_ENTRY_CATEGORY_VALUES!r}"
    )
