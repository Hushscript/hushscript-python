from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Final

from hushscript._errors import AuthenticationError, ConflictError, HushscriptError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from hushscript._clock import Clock
    from hushscript._log import RequestLog

HEARTBEAT_INTERVAL: Final = 120.0
WRONG_STATE: Final = "wrong_state"


class Heartbeat:
    """Keeps an upload alive: a ping every 120 s from create until complete (spec 8.5).

    A failed ping was already retried by the transport and is otherwise ignored, whatever it
    raised: only a clean `wrong_state` or `unauthorized` ends the loop. `wrong_state`
    ends the loop (the job has moved on); `unauthorized` ends it and is kept in `error` for the
    upload to raise.
    """

    def __init__(self, clock: Clock, log: RequestLog | None = None) -> None:
        self._clock = clock
        self._log = log
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: AuthenticationError | None = None

    def _keep_going(self, failure: HushscriptError) -> bool:
        if isinstance(failure, ConflictError) and failure.code == WRONG_STATE:
            return False
        if isinstance(failure, AuthenticationError):
            self.error = failure
            return False
        return True

    def _unexpected(self, failure: Exception) -> None:
        if self._log is not None:
            self._log.note(f"heartbeat ping failed ({type(failure).__name__}: {failure})")

    def run(self, ping: Callable[[], None]) -> None:
        while not self._clock.wait(self._stop, HEARTBEAT_INTERVAL):
            try:
                ping()
            except HushscriptError as failure:
                if not self._keep_going(failure):
                    return
            except Exception as failure:  # noqa: BLE001  # a ping that breaks must not end the beat
                self._unexpected(failure)

    async def arun(self, ping: Callable[[], Awaitable[None]]) -> None:
        while True:
            await self._clock.asleep(HEARTBEAT_INTERVAL)
            try:
                await ping()
            except HushscriptError as failure:
                if not self._keep_going(failure):
                    return
            except Exception as failure:  # noqa: BLE001  # a ping that breaks must not end the beat
                self._unexpected(failure)

    def start(self, ping: Callable[[], None]) -> None:
        self._thread = threading.Thread(target=self.run, args=(ping,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def raise_if_failed(self) -> None:
        if self.error is not None:
            raise self.error
