from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import hushscript._client as client_module
from conftest import TOKEN
from helpers import BASE_URL, FakeClock
from hushscript import AsyncHushscript, Hushscript

if TYPE_CHECKING:
    import threading

    import pytest

    from fakeapi import FakeApi

# The first bytes make it an MP3 to `sniff`; the length is what the API sees as the file size.
MP3 = b"ID3" + bytes(range(256)) * 40
SMALL = 15  # seconds, the shortest file the API takes


class PipeClock(FakeClock):
    """A fake clock for the pipeline tests: a heartbeat wait blocks until the upload stops it,
    unless the test grants `beats`, each of which returns at once."""

    def __init__(self, beats: int = 0) -> None:
        super().__init__()
        self.beats = beats

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        if self.beats > 0 and not stop.is_set():
            self.beats -= 1
            self.sleep(seconds)
            return False
        return stop.wait(30)

    async def asleep(self, seconds: float) -> None:
        if seconds == 120.0 and self.beats <= 0:  # a heartbeat wait; cancelled by the upload
            await asyncio.Event().wait()
        if seconds == 120.0:
            self.beats -= 1
        self.sleep(seconds)
        await asyncio.sleep(0)


def media(size: int = 9000) -> bytes:
    return (MP3 * (size // len(MP3) + 1))[:size]


def hs_for(
    monkeypatch: pytest.MonkeyPatch,
    api: FakeApi,
    clock: FakeClock | None = None,
    max_retries: int = 3,
) -> Hushscript:
    monkeypatch.setattr(client_module, "_sync_inner", api.sync)
    monkeypatch.setattr(client_module, "_async_inner", api.asynchronous)
    return Hushscript(TOKEN, base_url=BASE_URL, clock=clock or PipeClock(), max_retries=max_retries)


def async_hs_for(
    monkeypatch: pytest.MonkeyPatch,
    api: FakeApi,
    clock: FakeClock | None = None,
    max_retries: int = 3,
) -> AsyncHushscript:
    monkeypatch.setattr(client_module, "_sync_inner", api.sync)
    monkeypatch.setattr(client_module, "_async_inner", api.asynchronous)
    return AsyncHushscript(
        TOKEN, base_url=BASE_URL, clock=clock or PipeClock(), max_retries=max_retries
    )
