from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

    from hushscript._clock import Clock
    from hushscript._redact import Credentials


@dataclass(frozen=True, slots=True)
class Session:
    """What the pipeline needs from a client. `http` talks to the API (the retrying transport adds
    the token); `r2` is a second client with no token and no base URL, for the signed direct part
    URLs, which are never API requests."""

    clock: Clock
    credentials: Credentials


@dataclass(frozen=True, slots=True)
class SyncSession(Session):
    http: httpx.Client
    r2: httpx.Client


@dataclass(frozen=True, slots=True)
class AsyncSession(Session):
    http: httpx.AsyncClient
    r2: httpx.AsyncClient
