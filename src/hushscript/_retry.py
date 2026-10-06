from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import httpx

from ._pacing import CREATE_RATE_LIMIT_BACKOFF

if TYPE_CHECKING:
    import random

MAX_RETRY_AFTER: Final = 60.0
BACKOFF_CAP: Final = 8.0
BACKOFF_BASE: Final = 0.5
TOO_MANY_ACTIVE_JOBS: Final = "too_many_active_jobs"
TOO_MANY_REQUESTS: Final = 429

_NOT_SENT: Final = (httpx.ConnectError, httpx.ConnectTimeout)


class NetworkRetry(enum.Enum):
    ANY = "any"
    BEFORE_SENT = "before-sent"
    NONE = "none"


class RetryClass(enum.Enum):
    SAFE = "safe"
    PART = "part"
    COMPLETE = "complete"
    CREATE = "create"
    PURCHASE = "purchase"
    NEVER = "never"
    MUTATE = "mutate"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    statuses: frozenset[int]
    network: NetworkRetry
    cap: int | None = None


_SERVER_ERRORS: Final = frozenset(range(500, 600))
_POLICIES: Final = {
    RetryClass.SAFE: RetryPolicy(frozenset({429, 500, 502, 503, 504}), NetworkRetry.ANY),
    RetryClass.PART: RetryPolicy(frozenset({429}) | _SERVER_ERRORS, NetworkRetry.ANY),
    RetryClass.COMPLETE: RetryPolicy(frozenset({429}) | _SERVER_ERRORS, NetworkRetry.ANY),
    RetryClass.CREATE: RetryPolicy(frozenset({429}) | _SERVER_ERRORS, NetworkRetry.ANY),
    RetryClass.PURCHASE: RetryPolicy(frozenset({502, 503}), NetworkRetry.ANY, cap=1),
    RetryClass.NEVER: RetryPolicy(frozenset(), NetworkRetry.NONE),
    RetryClass.MUTATE: RetryPolicy(frozenset(), NetworkRetry.BEFORE_SENT),
}

_JOB: Final = r"/v1/uploads/[^/]+"
_ROUTES: Final = (
    ("POST", re.compile(rf"^{_JOB}/heartbeat$"), RetryClass.SAFE),
    ("PUT", re.compile(rf"^{_JOB}/parts/[^/]+$"), RetryClass.PART),
    ("POST", re.compile(rf"^{_JOB}/complete$"), RetryClass.COMPLETE),
    ("POST", re.compile(r"^/v1/uploads$"), RetryClass.CREATE),
    ("POST", re.compile(r"^/v1/billing/(purchase|setup-session)$"), RetryClass.PURCHASE),
    ("POST", re.compile(r"^/v1/agent/accounts/[^/]+/claim$"), RetryClass.NEVER),
    ("POST", re.compile(r"^/v1/agent/credentials/rotate$"), RetryClass.NEVER),
    ("POST", re.compile(r"^/v1/agent/accounts$"), RetryClass.NEVER),
)


def classify(method: str, path: str) -> RetryClass:
    """The spec 7.2 operation class of a request."""
    verb = method.upper()
    if verb in {"GET", "HEAD", "OPTIONS"}:
        return RetryClass.SAFE
    for route_method, pattern, retry_class in _ROUTES:
        if verb == route_method and pattern.match(path.rstrip("/") or "/"):
            return retry_class
    return RetryClass.MUTATE


def policy_for(retry_class: RetryClass) -> RetryPolicy:
    return _POLICIES[retry_class]


def backoff_delay(attempt: int, rng: random.Random) -> float:
    """Full jitter: random(0, min(8 s, 0.5 s * 2^attempt)); `attempt` counts retries from 0."""
    return rng.uniform(0.0, min(BACKOFF_CAP, BACKOFF_BASE * 2.0**attempt))


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one attempt produced: a response (status, Retry-After, slug) or a transport failure."""

    status: int | None = None
    retry_after: float | None = None
    slug: str | None = None
    failure: httpx.TransportError | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    retry: bool
    delay: float = 0.0


STOP: Final = Decision(retry=False)


def _after_failure(
    policy: RetryPolicy, attempt: int, failure: httpx.TransportError, rng: random.Random
) -> Decision:
    if policy.network is NetworkRetry.NONE:
        return STOP
    if policy.network is NetworkRetry.BEFORE_SENT and not isinstance(failure, _NOT_SENT):
        return STOP
    return Decision(retry=True, delay=backoff_delay(attempt, rng))


def _after_response(
    retry_class: RetryClass, attempt: int, outcome: Outcome, rng: random.Random
) -> Decision:
    if outcome.status is None or outcome.status not in policy_for(retry_class).statuses:
        return STOP
    if outcome.retry_after is not None:
        if outcome.retry_after > MAX_RETRY_AFTER:
            return STOP
        return Decision(retry=True, delay=outcome.retry_after)
    if retry_class is RetryClass.CREATE and outcome.status == TOO_MANY_REQUESTS:
        if outcome.slug == TOO_MANY_ACTIVE_JOBS or attempt >= len(CREATE_RATE_LIMIT_BACKOFF):
            return STOP
        return Decision(retry=True, delay=CREATE_RATE_LIMIT_BACKOFF[attempt])
    return Decision(retry=True, delay=backoff_delay(attempt, rng))


def decide(
    retry_class: RetryClass,
    attempt: int,
    max_retries: int,
    outcome: Outcome,
    rng: random.Random,
) -> Decision:
    """Whether to try again after attempt number `attempt` (0 is the first) and how long to wait."""
    policy = policy_for(retry_class)
    budget = max_retries if policy.cap is None else min(max_retries, policy.cap)
    if attempt >= budget:
        return STOP
    if outcome.failure is not None:
        return _after_failure(policy, attempt, outcome.failure, rng)
    return _after_response(retry_class, attempt, outcome, rng)
