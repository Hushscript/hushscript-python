# pyright: reportPrivateUsage=false
from __future__ import annotations

import threading

import pytest

from helpers import FakeClock
from hushscript import (
    AuthenticationError,
    ConflictError,
    NetworkError,
    RateLimitError,
)
from hushscript.transcribe.heartbeat import HEARTBEAT_INTERVAL, Heartbeat


def _run(failures: list[Exception]) -> tuple[Heartbeat, FakeClock, list[int]]:
    clock = FakeClock()
    heartbeat = Heartbeat(clock)
    calls: list[int] = []

    def ping() -> None:
        calls.append(len(calls) + 1)
        if failures:
            failure = failures.pop(0)
            raise failure

    heartbeat.run(ping)
    return heartbeat, clock, calls


def _wrong_state() -> ConflictError:
    return ConflictError("The job moved on.", code="wrong_state", status=409)


def _unauthorized() -> AuthenticationError:
    return AuthenticationError("No.", code="unauthorized", status=401)


def test_a_ping_is_sent_every_120_seconds_until_the_job_moves_on() -> None:
    failures: list[Exception] = [RateLimitError("slow", status=429)] * 2
    heartbeat, clock, calls = _run([*failures, _wrong_state()])
    assert HEARTBEAT_INTERVAL == 120
    assert clock.sleeps == [120, 120, 120]
    assert calls == [1, 2, 3]
    heartbeat.raise_if_failed()


def test_other_failures_are_ignored_and_the_loop_goes_on() -> None:
    _, clock, calls = _run(
        [NetworkError("down"), ConflictError("x", code="pat_limit"), _wrong_state()]
    )
    assert calls == [1, 2, 3]
    assert clock.sleeps == [120, 120, 120]


def test_unauthorized_stops_the_loop_and_is_kept_for_the_upload_to_raise() -> None:
    heartbeat, _, calls = _run([_unauthorized()])
    assert calls == [1]
    with pytest.raises(AuthenticationError):
        heartbeat.raise_if_failed()


def test_a_stopped_heartbeat_sends_nothing_more() -> None:
    clock = FakeClock()
    heartbeat = Heartbeat(clock)
    heartbeat._stop.set()
    heartbeat.run(lambda: pytest.fail("pinged after stop"))
    assert clock.sleeps == []


def test_the_thread_beats_and_stops_on_request() -> None:
    clock = FakeClock()
    heartbeat = Heartbeat(clock)
    pinged = threading.Event()

    def ping() -> None:
        pinged.set()
        heartbeat._stop.set()

    heartbeat.start(ping)
    assert pinged.wait(5)
    heartbeat.stop()
    assert heartbeat._thread is not None
    assert not heartbeat._thread.is_alive()


@pytest.mark.anyio
async def test_the_async_loop_beats_every_120_seconds_and_ends_on_wrong_state() -> None:
    clock = FakeClock()
    heartbeat = Heartbeat(clock)
    failures: list[Exception] = [NetworkError("down"), _wrong_state()]
    calls: list[int] = []

    async def ping() -> None:
        calls.append(1)
        raise failures.pop(0)

    await heartbeat.arun(ping)
    assert clock.sleeps == [120, 120]
    assert len(calls) == 2


@pytest.mark.anyio
async def test_the_async_loop_keeps_unauthorized() -> None:
    heartbeat = Heartbeat(FakeClock())

    async def ping() -> None:
        raise _unauthorized()

    await heartbeat.arun(ping)
    with pytest.raises(AuthenticationError):
        heartbeat.raise_if_failed()
