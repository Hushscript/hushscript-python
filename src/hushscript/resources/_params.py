from __future__ import annotations

from urllib.parse import quote

from hushscript.transcribe.preflight import invalid_option


def check_page_size(page_size: object) -> None:
    if page_size is None:
        return
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
        raise invalid_option("page_size must be a whole number of 1 or more.")


def path_id(resource_id: object) -> str:
    """An id as one percent-encoded path segment. An empty or non-string id, `.` and `..` (which a
    client or proxy would resolve to another route) and text that cannot be encoded as UTF-8 (a
    lone surrogate) are `invalid_option`, before any request."""
    if not isinstance(resource_id, str) or resource_id in {"", ".", ".."}:
        raise invalid_option("An id is a non-empty string other than . and ..")
    try:
        return quote(resource_id, safe="")
    except UnicodeEncodeError:
        raise invalid_option("An id must be text that encodes as UTF-8.") from None


def list_params(cursor: str | None, page_size: int | None) -> dict[str, str | int]:
    params: dict[str, str | int] = {}
    if page_size is not None:
        params["limit"] = page_size
    if cursor is not None:
        params["cursor"] = cursor
    return params
