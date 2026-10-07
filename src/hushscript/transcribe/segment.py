from __future__ import annotations

from urllib.parse import quote

_DOT_SEGMENTS = frozenset({"", ".", ".."})


def usable_segment(value: str) -> bool:
    """Whether an id the server or a resume token gave can stand as one path segment: not empty,
    not a dot segment (`GET /v1/jobs/..` is `GET /v1`), no slash or backslash, valid UTF-8."""
    if value in _DOT_SEGMENTS or "/" in value or "\\" in value:
        return False
    try:
        value.encode()
    except UnicodeEncodeError:
        return False
    return True


def segment(value: str) -> str:
    """`value` percent-encoded as one path segment; callers check `usable_segment` first where the
    id comes from outside."""
    return quote(value, safe="")
