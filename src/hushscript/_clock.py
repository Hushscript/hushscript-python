from __future__ import annotations

import asyncio
import time
from typing import Protocol


class Clock(Protocol):
    """Time source for pacing, backoff and polling; tests and the runner inject their own."""

    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...

    async def asleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    async def asleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
