from __future__ import annotations

import random
from typing import TYPE_CHECKING

import httpx

from hushscript._http import (
    AsyncRetryingTransport,
    RetryingTransport,
    TransportSettings,
)
from hushscript._log import RequestLog
from hushscript._redact import Credentials

if TYPE_CHECKING:
    from collections.abc import Sequence

Step = httpx.Response | Exception


class FakeClock:
    def __init__(self) -> None:
        self.time = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.time += seconds

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


class Script:
    """Answers each request with the next step; an Exception step is raised as a failure."""

    def __init__(self, steps: Sequence[Step]) -> None:
        self.steps = list(steps)
        self.requests: list[httpx.Request] = []

    def _next(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step = self.steps.pop(0) if len(self.steps) > 1 else self.steps[0]
        if isinstance(step, Exception):
            raise step
        return step

    def sync(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._next)

    def asynchronous(self) -> httpx.MockTransport:
        async def handler(request: httpx.Request) -> httpx.Response:
            return self._next(request)

        return httpx.MockTransport(handler)

    @property
    def calls(self) -> int:
        return len(self.requests)


def settings_for(
    clock: FakeClock,
    *,
    max_retries: int = 3,
    token: str | None = None,
    level: str = "off",
) -> TransportSettings:
    return TransportSettings(
        clock=clock,
        log=RequestLog(level),
        credentials=Credentials(token),
        max_retries=max_retries,
        rng=random.Random(7),  # noqa: S311  # deterministic jitter for tests
    )


def sync_client(
    script: Script,
    clock: FakeClock,
    *,
    max_retries: int = 3,
    token: str | None = None,
    level: str = "off",
) -> httpx.Client:
    settings = settings_for(clock, max_retries=max_retries, token=token, level=level)
    return httpx.Client(
        base_url="http://127.0.0.1:4010",
        transport=RetryingTransport(script.sync(), settings),
    )


def async_client(
    script: Script,
    clock: FakeClock,
    *,
    max_retries: int = 3,
    token: str | None = None,
    level: str = "off",
) -> httpx.AsyncClient:
    settings = settings_for(clock, max_retries=max_retries, token=token, level=level)
    return httpx.AsyncClient(
        base_url="http://127.0.0.1:4010",
        transport=AsyncRetryingTransport(script.asynchronous(), settings),
    )


def reply(
    status: int,
    body: object = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    if body is None:
        return httpx.Response(status, headers=headers, text="status text")
    return httpx.Response(status, json=body, headers=headers)


def error_body(slug: str, code: int, **extra: object) -> dict[str, object]:
    return {"error": slug, "code": code, **extra}
