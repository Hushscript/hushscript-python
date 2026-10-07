from __future__ import annotations

import threading
from collections import deque
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ._clock import Clock

CREATES_PER_WINDOW: Final = 4
WINDOW_SECONDS: Final = 60.0
CREATE_RATE_LIMIT_BACKOFF: Final = (15.0, 30.0, 60.0)
ACTIVE_JOBS_WAIT: Final = 30.0
ACTIVE_JOBS_MAX_TRIES: Final = 10
ACTIVE_JOBS_RETRIES: Final = ACTIVE_JOBS_MAX_TRIES - 1


class TokenBucket:
    """Paces `POST /v1/uploads` to 4 per 60 s per client (spec 7.5).

    `reserve()` books the next slot and says how long the caller must wait before using it, so the
    sync and async callers sleep on their own clock method.
    """

    def __init__(
        self,
        clock: Clock,
        capacity: int = CREATES_PER_WINDOW,
        window: float = WINDOW_SECONDS,
    ) -> None:
        self._clock = clock
        self._capacity = capacity
        self._window = window
        self._slots: deque[float] = deque()
        self._lock = threading.Lock()

    def reserve(self) -> float:
        with self._lock:
            return self._reserve()

    def _reserve(self) -> float:
        now = self._clock.now()
        while self._slots and self._slots[0] <= now - self._window:
            self._slots.popleft()
        if len(self._slots) < self._capacity:
            self._slots.append(now)
            return 0.0
        wait = self._slots[0] + self._window - now
        self._slots.popleft()
        self._slots.append(now + wait)
        return wait
