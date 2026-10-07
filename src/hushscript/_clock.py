from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import threading


class Clock(Protocol):
    """Time source for pacing, backoff and polling; tests and the runner inject their own."""

    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        """Sleeps up to `seconds` but wakes as soon as `stop` is set; True when it was set."""
        ...

    async def asleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        return stop.wait(seconds)

    async def asleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
