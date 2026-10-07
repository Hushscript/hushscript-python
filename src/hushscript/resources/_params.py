from __future__ import annotations

from urllib.parse import quote

from hushscript.transcribe.preflight import invalid_option


def check_page_size(page_size: object) -> None:
    if page_size is None:
        return
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
        raise invalid_option("page_size must be a whole number of 1 or more.")


def path_id(resource_id: object) -> str:
    """An id as one path segment: nothing in it can reach another route."""
    if not isinstance(resource_id, str) or not resource_id:
        raise invalid_option("An id is a non-empty string.")
    return quote(resource_id, safe="")


def list_params(cursor: str | None, page_size: int | None) -> dict[str, str | int]:
    params: dict[str, str | int] = {}
    if page_size is not None:
        params["limit"] = page_size
    if cursor is not None:
        params["cursor"] = cursor
    return params
