"""`hs.api` keeps one promise: nothing but an SDK error leaves it (R61).

The generated functions parse the answer after the transport has returned it, reading its JSON and
building a model from it, and a body that is not what they expect raises a bare `JSONDecodeError`,
`KeyError` or `TypeError`. The transport cannot see a call is generated, but the generated function
is on the stack that called it, so it runs that function's own parser on the answer before handing
it back and turns a failure into an SDK error. Generated code is never edited (spec section 5).
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import TYPE_CHECKING, Final

from ._errors import HushscriptError, error_from_response, redacted_cause
from ._response import unreadable_response

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

    from ._redact import Credentials

GENERATED_MODULES: Final = "hushscript.generated.api."
_LENIENT_CLIENT: Final = SimpleNamespace(raise_on_unexpected_status=False)
"""Stands in for the client: an undocumented status is the generated function's own business."""


def generated_parser() -> Callable[..., object] | None:
    """The `_parse_response` of the generated operation that is making the current request, or
    None when the request is not one."""
    frame = inspect.currentframe()
    try:
        while frame is not None:
            name = frame.f_globals.get("__name__")
            if isinstance(name, str) and name.startswith(GENERATED_MODULES):
                parse = frame.f_globals.get("_parse_response")
                return parse if callable(parse) else None
            frame = frame.f_back
        return None
    finally:
        del frame


def unusable_answer(
    parse: Callable[..., object], response: httpx.Response, credentials: Credentials | None
) -> HushscriptError | None:
    """The SDK error for an answer the generated parser cannot read, or None when it can. A 2xx is
    `bad_response`; any other status is the error the friendly layer would raise for it. The error
    is returned, not raised, so the original is on neither its cause nor its `__context__`."""
    try:
        parse(client=_LENIENT_CLIENT, response=response)
    except Exception as failure:  # noqa: BLE001  # whatever the generated parser trips on
        if response.is_success:
            return unreadable_response(response, failure, credentials)
        error = error_from_response(response, credentials=credentials)
        error.__cause__ = redacted_cause(failure, credentials)
        return error
    return None
