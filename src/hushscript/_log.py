from __future__ import annotations

import logging
import sys
from typing import Final

from ._redact import redact

LOG_LEVELS: Final = ("off", "debug")
_LOGGER: Final = logging.getLogger("hushscript")


class RequestLog:
    """One line per attempt: method, path, status, attempt, duration and retry delay (spec 10).

    Never headers, query strings, bodies, titles or transcript text; the caller passes a path
    without a query and direct-to-R2 URLs arrive as `r2:part/{n}`.
    """

    def __init__(self, level: str = "off") -> None:
        self.enabled = level == "debug"
        if self.enabled:
            _LOGGER.setLevel(logging.DEBUG)
            if not _LOGGER.handlers:
                handler = logging.StreamHandler(sys.stderr)
                handler.setFormatter(logging.Formatter("%(message)s"))
                _LOGGER.addHandler(handler)

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
