from __future__ import annotations

import re
from typing import Final
from urllib.parse import quote

from ._json import as_dict, as_list

REDACTED: Final = "hsr…[redacted]"
TOKEN_PATTERN: Final = re.compile(r"hsr\d+:[a-z]+:pat\.[0-9a-f]+\.[0-9a-f]+")
MIN_SECRET_TAIL: Final = 16
_WHOLE_TOKEN_FORMS: Final = 2
"""A shorter echoed piece of a token is an ordinary substring, not worth redacting everywhere."""


def _patterns(token: str) -> list[re.Pattern[str]]:
    """What an API could echo of `token`, most specific first: the whole token as it is and
    percent-encoded, then what follows `pat.` and the bare secret after the last dot. Matching
    ignores case. A later piece is only ever a substring of an earlier one, so the order keeps the
    id from being left behind."""
    # surrogatepass: a lone surrogate in a registered secret still has a percent-encoded form
    pieces = [token, quote(token, safe="", errors="surrogatepass")]
    _, found, tail = token.partition("pat.")
    if found:
        pieces.append(tail)
    pieces.append(token.rpartition(".")[2])
    return [
        re.compile(re.escape(piece), re.IGNORECASE)
        for index, piece in enumerate(pieces)
        if piece and (index < _WHOLE_TOKEN_FORMS or len(piece) >= MIN_SECRET_TAIL)
    ]


def redact(text: str) -> str:
    return TOKEN_PATTERN.sub(REDACTED, text)


QUERY_REDACTED: Final = "?[redacted]"
_URL_QUERY: Final = re.compile(
    # a URL with any scheme, or a path at the start of the text or after a space, quote, bracket
    # or `=`; a query stops at a space, quote, angle bracket, `#` or `)`
    r"((?:\b[a-z][a-z0-9+.-]*://[^\s\"'<>?#]+)|(?:(?<![^\s\"'(\[<=])/[^\s\"'<>?#]*))"
    r"\?[^\s\"'<>#)]+",
    re.IGNORECASE,
)


def redact_queries(text: str) -> str:
    """R96: every URL or path in `text` keeps its scheme, host and path; its query string, which
    holds a signed URL's signature, becomes `?[redacted]`."""
    return _URL_QUERY.sub(lambda match: match.group(1) + QUERY_REDACTED, text)


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
            for pattern in _patterns(token):
                text = pattern.sub(REDACTED, text)
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
