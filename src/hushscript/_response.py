from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from ._errors import ApiError, raise_for_response

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

    from ._redact import Credentials

T = TypeVar("T")


class BadBodyError(ValueError):
    """A 2xx body that parses as JSON but not into the shape the SDK needs."""


def bad_response(response: httpx.Response, what: str) -> ApiError:
    """Spec 9.2: an unusable 2xx body, with the actual status and no numeric code."""
    return ApiError(
        f"The API's {what} could not be used.", code="bad_response", status=response.status_code
    )


def json_body(response: httpx.Response, credentials: Credentials) -> object:
    """The JSON of a 2xx response; a non-2xx one raises the spec 9.2 error."""
    raise_for_response(response, credentials=credentials)
    try:
        return response.json()
    except (
        ValueError,
        RecursionError,
    ) as failure:  # a deeply nested body is not JSON the SDK reads
        raise bad_response(response, "response (not JSON)") from failure


def parsed(response: httpx.Response, credentials: Credentials, parse: Callable[[object], T]) -> T:
    """`parse` of the JSON of a 2xx response; a body it cannot use is `bad_response`."""
    body = json_body(response, credentials)
    try:
        return parse(body)
    except BadBodyError as failure:
        raise bad_response(response, str(failure)) from failure
