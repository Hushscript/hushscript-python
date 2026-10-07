from __future__ import annotations

import logging
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Final, cast

import httpx

from ._redact import redact

if TYPE_CHECKING:
    from collections.abc import Generator

LOG_LEVELS: Final = ("off", "debug")
_LOGGER: Final = logging.getLogger("hushscript")

# The label of the signed R2 request this thread or task is sending, or None. httpx logs every
# request's full URL at INFO on its own logger ("HTTP Request: PUT <url>"), and a signed part URL
# carries the signature in its query (spec 10: R2 URLs only ever appear as `r2:part/{n}`).
_SIGNED_REQUEST: ContextVar[str | None] = ContextVar("hushscript_signed_request", default=None)


_URL_TEXT: Final = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"<>]+")
# The query keys that make a URL signed: S3/R2 presigned (X-Amz-*), the mock's `sig`, and the
# generic names other signers use.
_SIGNED_QUERY: Final = re.compile(
    r"[?&](?:sig|signature|token|expires|x-amz-[a-z0-9-]+|x-goog-[a-z0-9-]+)=", re.IGNORECASE
)


def _looks_signed(url: str) -> bool:
    return _SIGNED_QUERY.search(url) is not None


def _hide(value: object, label: str) -> object:
    """`value` with every signed-looking URL in it swapped for `label`."""
    if isinstance(value, httpx.URL):
        return label if _looks_signed(str(value)) else value
    if isinstance(value, str):
        return _URL_TEXT.sub(lambda m: label if _looks_signed(m.group(0)) else m.group(0), value)
    return value


class _SignedUrlFilter(logging.Filter):
    """Swaps the URL in an httpx record for the request's label while a signed request is out.

    It only rewrites records logged by the thread or task that is sending the signed request, so
    other httpx users in the process keep their log lines, and it never touches a level. A URL
    that httpx has already formatted into the message, or put in a mapping argument, goes too.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        label = _SIGNED_REQUEST.get()
        if label is None:
            return True
        if isinstance(record.msg, str):
            record.msg = _hide(record.msg, label)
        args: object = record.args
        if isinstance(args, tuple):
            record.args = tuple(
                label if isinstance(arg, (str, httpx.URL)) and "://" in str(arg) else arg
                for arg in cast("tuple[object, ...]", args)
            )
        elif isinstance(args, dict):
            record.args = {
                key: _hide(item, label) for key, item in cast("dict[str, object]", args).items()
            }
        return True


_SIGNED_URL_FILTER: Final = _SignedUrlFilter()


@contextmanager
def hiding_signed_url(label: str) -> Generator[None]:
    """Within the block, httpx's own request log shows `label` where the signed URL would be."""
    token = _SIGNED_REQUEST.set(label)
    try:
        yield
    finally:
        _SIGNED_REQUEST.reset(token)


class RequestLog:
    """One line per attempt: method, path, status, attempt, duration and retry delay (spec 10).

    Never headers, query strings, bodies, titles or transcript text; the caller passes a path
    without a query and direct-to-R2 URLs arrive as `r2:part/{n}`.
    """

    def __init__(self, level: str = "off") -> None:
        # httpx logs on its own, whatever our level; the filter is a no-op until a
        # signed request is out. Adding it twice is harmless.
        logging.getLogger("httpx").addFilter(_SIGNED_URL_FILTER)
        self.enabled = level == "debug"
        if self.enabled:
            _LOGGER.setLevel(logging.DEBUG)
            if not _LOGGER.handlers:
                handler = logging.StreamHandler(sys.stderr)
                handler.setFormatter(logging.Formatter("%(message)s"))
                _LOGGER.addHandler(handler)

    def note(self, message: str) -> None:
        """A line outside the request/attempt shape, such as a heartbeat that failed; redacted."""
        if self.enabled:
            _LOGGER.debug(redact(f"hushscript {message}"))

    def attempt(  # one call site per field of the line
        self,
        method: str,
        path: str,
        status: int | None,
        attempt: int,
        duration_ms: float,
        retry_delay: float | None,
    ) -> None:
        if not self.enabled:
            return
        outcome = "error" if status is None else str(status)
        delay = "" if retry_delay is None else f" retry_in={retry_delay:g}s"
        _LOGGER.debug(
            redact(
                f"hushscript {method} {path} {outcome} attempt={attempt} {duration_ms:.0f}ms{delay}"
            )
        )
