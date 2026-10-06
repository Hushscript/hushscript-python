from __future__ import annotations

import random

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st

from hushscript._retry import (
    MAX_RETRY_AFTER,
    NetworkRetry,
    Outcome,
    RetryClass,
    backoff_delay,
    classify,
    decide,
    policy_for,
)

RNG = random.Random(1)  # noqa: S311  # deterministic jitter for tests
CONNECT = httpx.ConnectError("refused")
READ = httpx.ReadError("reset")


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "/v1/account", RetryClass.SAFE),
        ("GET", "/v1/uploads/j1/part-urls", RetryClass.SAFE),
        ("HEAD", "/v1/account", RetryClass.SAFE),
        ("POST", "/v1/uploads/j1/heartbeat", RetryClass.SAFE),
        ("PUT", "/v1/uploads/j1/parts/3", RetryClass.PART),
        ("POST", "/v1/uploads/j1/complete", RetryClass.COMPLETE),
        ("POST", "/v1/uploads", RetryClass.CREATE),
        ("POST", "/v1/uploads/", RetryClass.CREATE),
        ("POST", "/v1/billing/purchase", RetryClass.PURCHASE),
        ("POST", "/v1/billing/setup-session", RetryClass.PURCHASE),
        ("POST", "/v1/agent/accounts/sg_1/claim", RetryClass.NEVER),
        ("POST", "/v1/agent/credentials/rotate", RetryClass.NEVER),
        ("POST", "/v1/agent/accounts", RetryClass.NEVER),
        ("POST", "/v1/billing/cards/default", RetryClass.MUTATE),
        ("PATCH", "/v1/org/members/u1", RetryClass.MUTATE),
        ("DELETE", "/v1/org/transcripts/t1/hold", RetryClass.MUTATE),
    ],
)
def test_classify_follows_the_spec_7_2_table(method: str, path: str, expected: RetryClass) -> None:
    assert classify(method, path) is expected


def test_the_purchase_class_never_retries_a_4xx() -> None:
    policy = policy_for(RetryClass.PURCHASE)
    assert policy.statuses == {502, 503}
    assert policy.cap == 1
    assert not any(400 <= status < 500 for status in policy.statuses)


@given(st.integers(min_value=0, max_value=40), st.integers(min_value=0, max_value=2**32))
def test_backoff_is_full_jitter_within_the_cap(attempt: int, seed: int) -> None:
    delay = backoff_delay(attempt, random.Random(seed))  # noqa: S311  # seeded for the property
    assert 0.0 <= delay <= min(8.0, 0.5 * 2.0**attempt)


def test_backoff_reaches_the_eight_second_cap() -> None:
    assert max(backoff_delay(10, random.Random(seed)) for seed in range(200)) > 7.0  # noqa: S311


def test_a_retry_after_above_sixty_stops_retrying() -> None:
    outcome = Outcome(status=429, retry_after=MAX_RETRY_AFTER + 1)
    assert not decide(RetryClass.SAFE, 0, 3, outcome, RNG).retry


def test_a_retry_after_overrides_the_backoff() -> None:
    decision = decide(RetryClass.SAFE, 0, 3, Outcome(status=429, retry_after=7), RNG)
    assert (decision.retry, decision.delay) == (True, 7.0)
    assert decide(RetryClass.SAFE, 0, 3, Outcome(status=429, retry_after=60), RNG).delay == 60.0


def test_retries_stop_at_max_retries() -> None:
    outcome = Outcome(status=503)
    assert [decide(RetryClass.SAFE, n, 3, outcome, RNG).retry for n in range(5)] == [
        True,
        True,
        True,
        False,
        False,
    ]
    assert not decide(RetryClass.SAFE, 0, 0, outcome, RNG).retry


def test_the_purchase_budget_is_one_whatever_max_retries_says() -> None:
    outcome = Outcome(status=502)
    assert decide(RetryClass.PURCHASE, 0, 9, outcome, RNG).retry
    assert not decide(RetryClass.PURCHASE, 1, 9, outcome, RNG).retry


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 429, 500, 504])
def test_the_purchase_class_ignores_other_statuses(status: int) -> None:
    assert not decide(RetryClass.PURCHASE, 0, 3, Outcome(status=status), RNG).retry


@pytest.mark.parametrize(
    ("status", "retried"),
    [
        (429, True),
        (500, True),
        (502, True),
        (503, True),
        (504, True),
        (404, False),
        (501, False),
        (200, False),
    ],
)
def test_the_safe_class_statuses(status: int, retried: bool) -> None:  # noqa: FBT001
    assert decide(RetryClass.SAFE, 0, 3, Outcome(status=status), RNG).retry is retried


@pytest.mark.parametrize("retry_class", [RetryClass.PART, RetryClass.COMPLETE, RetryClass.CREATE])
def test_upload_classes_retry_any_5xx(retry_class: RetryClass) -> None:
    assert decide(retry_class, 0, 3, Outcome(status=501), RNG).retry
    assert not decide(retry_class, 0, 3, Outcome(status=403), RNG).retry


def test_create_backs_off_15_30_60_on_a_429_without_retry_after() -> None:
    outcome = Outcome(status=429)
    delays = [decide(RetryClass.CREATE, n, 5, outcome, RNG) for n in range(4)]
    assert [(d.retry, d.delay) for d in delays] == [
        (True, 15.0),
        (True, 30.0),
        (True, 60.0),
        (False, 0.0),
    ]


def test_create_retries_too_many_active_jobs_nine_times_whatever_max_retries_says() -> None:
    outcome = Outcome(status=429, slug="too_many_active_jobs")
    decisions = [decide(RetryClass.CREATE, n, 1, outcome, RNG) for n in range(11)]
    assert [d.retry for d in decisions] == [True] * 9 + [False, False]
    assert {d.delay for d in decisions[:9]} == {30.0}
    assert not decide(RetryClass.CREATE, 0, 0, outcome, RNG).retry


def test_create_honors_retry_after_when_present() -> None:
    assert decide(RetryClass.CREATE, 0, 3, Outcome(status=429, retry_after=2), RNG).delay == 2.0


@pytest.mark.parametrize(
    ("retry_class", "failure", "retried"),
    [
        (RetryClass.SAFE, CONNECT, True),
        (RetryClass.SAFE, READ, True),
        (RetryClass.PURCHASE, READ, True),
        (RetryClass.MUTATE, CONNECT, True),
        (RetryClass.MUTATE, httpx.ConnectTimeout("slow"), True),
        (RetryClass.MUTATE, READ, False),
        (RetryClass.MUTATE, httpx.ReadTimeout("slow"), False),
        (RetryClass.NEVER, CONNECT, False),
        (RetryClass.NEVER, READ, False),
    ],
)
def test_network_failures_by_class(
    retry_class: RetryClass,
    failure: httpx.TransportError,
    retried: bool,  # noqa: FBT001
) -> None:
    assert decide(retry_class, 0, 3, Outcome(failure=failure), RNG).retry is retried


def test_a_missing_status_is_never_retried() -> None:
    assert not decide(RetryClass.SAFE, 0, 3, Outcome(), RNG).retry


def test_policy_table_covers_every_class() -> None:
    assert {policy_for(c).network for c in RetryClass} == set(NetworkRetry)
