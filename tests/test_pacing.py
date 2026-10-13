from __future__ import annotations

import pytest

from helpers import FakeClock
from hushscript._clock import SystemClock
from hushscript._pacing import TokenBucket


def test_four_creates_pass_at_once_and_the_fifth_waits_for_the_window() -> None:
    clock = FakeClock()
    bucket = TokenBucket(clock)
    assert [bucket.reserve() for _ in range(4)] == [0.0, 0.0, 0.0, 0.0]
    assert bucket.reserve() == 60.0


def test_slots_come_back_as_the_window_moves() -> None:
    clock = FakeClock()
    bucket = TokenBucket(clock)
    for _ in range(4):
        bucket.reserve()
    clock.time = 30.0
    assert bucket.reserve() == 30.0
    clock.time = 61.0
    assert bucket.reserve() == 0.0


def test_six_creates_in_a_loop_take_at_least_a_window() -> None:
    clock = FakeClock()
    bucket = TokenBucket(clock)
    for _ in range(6):
        clock.sleep(bucket.reserve())
    assert clock.time >= 60.0


def test_the_system_clock_ticks_and_sleeps() -> None:
    clock = SystemClock()
    before = clock.now()
    clock.sleep(0)
    assert clock.now() >= before


@pytest.mark.anyio
async def test_the_system_clock_sleeps_asynchronously() -> None:
    await SystemClock().asleep(0)
