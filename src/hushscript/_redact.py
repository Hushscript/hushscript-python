from __future__ import annotations

import re
from typing import Final

from ._json import as_dict, as_list

REDACTED: Final = "hsr…[redacted]"
TOKEN_PATTERN: Final = re.compile(r"hsr\d+:[a-z]+:pat\.[0-9a-f]+\.[0-9a-f]+")


def redact(text: str) -> str:
    return TOKEN_PATTERN.sub(REDACTED, text)


class Secret:
    """A token or a signed URL held at rest: nothing prints, pickles or copies its text.

    `repr`, `str`, `format`, `pprint`, `vars` and logging show the redaction marker. A pickle holds
    an empty secret, and a copy is the same holder (it is immutable). `reveal()` is the one way to
    the text.
    """

    __slots__ = ("_text",)

    def __init__(self, text: str = "") -> None:
        self._text = text

    def reveal(self) -> str:
        return self._text

    def __bool__(self) -> bool:
        return bool(self._text)

    def __repr__(self) -> str:
        return "Secret(<redacted>)"

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:
        return format(REDACTED, format_spec)

    def __reduce__(self) -> tuple[type[Secret], tuple[str]]:
        return (Secret, ("",))

    def __copy__(self) -> Secret:
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> Secret:
        return self


class Credentials:
    """The API token and every earlier one, kept out of every representation.

    The token is held here and nowhere else in the client: not in a header on the httpx client, not
    in a dataclass field. The transport reads it per request.
    """

    __slots__ = ("_known", "_tokens")

    def __init__(self, token: str | None = None) -> None:
        self._tokens: list[str] = []
        self._known: list[str] = []
        if token:
            self._tokens.append(token)

    @property
    def token(self) -> str | None:
        return self._tokens[-1] if self._tokens else None

    def replace(self, token: str) -> None:
        self._tokens.append(token)

    def remember(self, token: str) -> None:
        """Scrubs `token` from every text from now on without making it the one the client sends."""
        if token and token not in self._known:
            self._known.append(token)

    def scrub(self, text: str) -> str:
        for token in (*self._tokens, *self._known):
            text = text.replace(token, REDACTED)
        return redact(text)

    def scrub_value(self, value: object) -> object:
        if isinstance(value, str):
            return self.scrub(value)
        mapping = as_dict(value)
        if mapping is not None:
            return {self.scrub(key): self.scrub_value(item) for key, item in mapping.items()}
        items = as_list(value)
        if items is not None:
            return [self.scrub_value(item) for item in items]
        return value

    def __repr__(self) -> str:
        return "Credentials(<redacted>)"

    def __reduce__(self) -> str | tuple[object, ...]:
        raise TypeError("credentials cannot be pickled")
