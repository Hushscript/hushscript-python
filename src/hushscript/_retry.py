from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import httpx

from ._pacing import ACTIVE_JOBS_RETRIES, ACTIVE_JOBS_WAIT, CREATE_RATE_LIMIT_BACKOFF

if TYPE_CHECKING:
    import random

MAX_RETRY_AFTER: Final = 60.0
BACKOFF_CAP: Final = 8.0
BACKOFF_BASE: Final = 0.5
TOO_MANY_ACTIVE_JOBS: Final = "too_many_active_jobs"
TOO_MANY_REQUESTS: Final = 429

# Spec 7.4: only DNS, connect, TLS-handshake and pool-wait failures happen before the request body
# is written; httpx maps the first three to ConnectError/ConnectTimeout. Everything else is "sent".
_NOT_SENT: Final = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


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

CLAIM: Final = "claim"
ROTATE: Final = "rotate"
SIGNUP: Final = "signup"

_JOB: Final = r"/v1/uploads/[^/]+"
# (method, path, class, name of a route whose lost response needs its own hint)
_ROUTES: Final = (
    ("POST", re.compile(rf"^{_JOB}/heartbeat$"), RetryClass.SAFE, None),
    ("PUT", re.compile(rf"^{_JOB}/parts/[^/]+$"), RetryClass.PART, None),
    ("POST", re.compile(rf"^{_JOB}/complete$"), RetryClass.COMPLETE, None),
    ("POST", re.compile(r"^/v1/uploads$"), RetryClass.CREATE, None),
    ("POST", re.compile(r"^/v1/billing/(purchase|setup-session)$"), RetryClass.PURCHASE, None),
    ("POST", re.compile(r"^/v1/agent/accounts/[^/]+/claim$"), RetryClass.NEVER, CLAIM),
    ("POST", re.compile(r"^/v1/agent/credentials/rotate$"), RetryClass.NEVER, ROTATE),
    ("POST", re.compile(r"^/v1/agent/accounts$"), RetryClass.NEVER, SIGNUP),
)


def _route(method: str, path: str) -> tuple[RetryClass, str | None] | None:
    verb = method.upper()
    for route_method, pattern, retry_class, name in _ROUTES:
        if verb == route_method and pattern.match(path.rstrip("/") or "/"):
            return retry_class, name
    return None


def classify(method: str, path: str) -> RetryClass:
    """The spec 7.2 operation class of a request; `path` is relative to the base URL."""
    route = _route(method, path)
    if route is not None:
        return route[0]
    return RetryClass.SAFE if method.upper() in {"GET", "HEAD", "OPTIONS"} else RetryClass.MUTATE


def unrecoverable_route(method: str, path: str) -> str | None:
    """`claim`, `rotate` or `signup` when the request is one of the spec 7.4 routes, else None."""
    route = _route(method, path)
    return None if route is None else route[1]


def is_not_sent(failure: httpx.TransportError) -> bool:
    """True when the failure happened before the request body was written (spec 7.4)."""
    return isinstance(failure, _NOT_SENT)


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
    if policy.network is NetworkRetry.BEFORE_SENT and not is_not_sent(failure):
        return STOP
    return Decision(retry=True, delay=backoff_delay(attempt, rng))


RATE_LIMITED: Final = "rate_limited"
ACTIVE_JOBS: Final = "active_jobs"


def create_limit_kind(retry_class: RetryClass, outcome: Outcome) -> str | None:
    """The 429 schedule (spec 7.5) a response belongs to: `active_jobs`, `rate_limited` or None."""
    if retry_class is not RetryClass.CREATE or outcome.status != TOO_MANY_REQUESTS:
        return None
    return ACTIVE_JOBS if outcome.slug == TOO_MANY_ACTIVE_JOBS else RATE_LIMITED


def _after_create_rate_limit(own_429: int, outcome: Outcome) -> Decision:
    if outcome.slug == TOO_MANY_ACTIVE_JOBS:
        return Decision(retry=True, delay=ACTIVE_JOBS_WAIT)
    if own_429 >= len(CREATE_RATE_LIMIT_BACKOFF):
        return STOP
    return Decision(retry=True, delay=CREATE_RATE_LIMIT_BACKOFF[own_429])


def _after_response(
    retry_class: RetryClass, attempt: int, own_429: int, outcome: Outcome, rng: random.Random
) -> Decision:
    if outcome.status is None or outcome.status not in policy_for(retry_class).statuses:
        return STOP
    if outcome.retry_after is not None:
        if outcome.retry_after > MAX_RETRY_AFTER:
            return STOP
        return Decision(retry=True, delay=outcome.retry_after)
    if create_limit_kind(retry_class, outcome) is not None:
        return _after_create_rate_limit(own_429, outcome)
    return Decision(retry=True, delay=backoff_delay(attempt, rng))


def _exhausted(
    retry_class: RetryClass, attempt: int, own_429: int, max_retries: int, outcome: Outcome
) -> bool:
    if create_limit_kind(retry_class, outcome) == ACTIVE_JOBS:
        # Spec 7.5: ten tries whatever max_retries says, counted over active-jobs 429s only; only
        # max_retries=0 turns this off.
        return max_retries == 0 or own_429 >= ACTIVE_JOBS_RETRIES
    cap = policy_for(retry_class).cap
    return attempt >= (max_retries if cap is None else min(max_retries, cap))


def decide(  # the attempt counters are separate on purpose (spec 7.2)
    retry_class: RetryClass,
    attempt: int,
    max_retries: int,
    outcome: Outcome,
    rng: random.Random,
    own_429: int | None = None,
) -> Decision:
    """Whether to try again after attempt number `attempt` (0 is the first) and how long to wait.

    `own_429` is how many earlier responses were 429s of the same schedule as this one; the 429
    schedules count only those, not retries of other kinds. It defaults to `attempt`.
    """
    own = attempt if own_429 is None else own_429
    if _exhausted(retry_class, attempt, own, max_retries, outcome):
        return STOP
    if outcome.failure is not None:
        return _after_failure(policy_for(retry_class), attempt, outcome.failure, rng)
    return _after_response(retry_class, attempt, own, outcome, rng)
