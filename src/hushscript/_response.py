from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from ._errors import ApiError, describe_failure, raise_for_response, redacted_cause
from ._json import loads

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


def unreadable_response(
    response: httpx.Response, failure: BaseException, credentials: Credentials | None
) -> ApiError:
    """`bad_response` for a body the SDK could not read, naming the original's type and redacted
    message (R86). Its cause is a stand-in: a JSON error keeps the whole body it read, which may
    hold a token or a claim secret."""
    error = ApiError(
        f"The API's response could not be used ({describe_failure(failure, credentials)}).",
        code="bad_response",
        status=response.status_code,
    )
    error.__cause__ = redacted_cause(failure, credentials)
    return error


def json_body(response: httpx.Response, credentials: Credentials) -> object:
    """The JSON of a 2xx response; a non-2xx one raises the spec 9.2 error."""
    raise_for_response(response, credentials=credentials)
    try:
        return loads(response.content)
    except (
        ValueError,
        RecursionError,
    ) as failure:  # a deeply nested body is not JSON the SDK reads
        # Raised once the handler has ended, so the JSON error is not its context either.
        failed = unreadable_response(response, failure, credentials)
    raise failed


def parsed(response: httpx.Response, credentials: Credentials, parse: Callable[[object], T]) -> T:
    """`parse` of the JSON of a 2xx response; a body it cannot use is `bad_response`."""
    body = json_body(response, credentials)
    try:
        return parse(body)
    except BadBodyError as failure:
        raise bad_response(response, str(failure)) from failure
