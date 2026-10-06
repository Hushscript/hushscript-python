from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import httpx

from ._errors import NetworkError, OutcomeUnknownError, parse_retry_after
from ._json import as_dict
from ._retry import TOO_MANY_REQUESTS, Decision, Outcome, RetryClass, classify, decide

if TYPE_CHECKING:
    from ._clock import Clock
    from ._log import RequestLog
    from ._redact import Credentials

LABEL_EXTENSION: Final = "hushscript_label"
CLASS_EXTENSION: Final = "hushscript_class"
ANONYMOUS_EXTENSION: Final = "hushscript_anonymous"

_UNKNOWN_HINTS: Final = {
    "claim": (
        "The claim may have succeeded. Retrying will fail with agent_claim_invalid. "
        "If you have no token, contact support with the signup id."
    ),
    "rotate": (
        "The old token may already be revoked. Try a request with it; if it fails, "
        "the new token was lost and the account needs support."
    ),
}


@dataclass(slots=True)
class TransportSettings:
    clock: Clock
    log: RequestLog
    credentials: Credentials | None
    max_retries: int
    rng: random.Random = field(default_factory=random.SystemRandom)


def _retry_class(request: httpx.Request) -> RetryClass:
    override = request.extensions.get(CLASS_EXTENSION)
    if isinstance(override, RetryClass):
        return override
    return classify(request.method, request.url.path)


def _label(request: httpx.Request) -> str:
    label = request.extensions.get(LABEL_EXTENSION)
    return label if isinstance(label, str) else request.url.path


def _authorize(request: httpx.Request, settings: TransportSettings) -> None:
    token = None if settings.credentials is None else settings.credentials.token
    if token is not None and not request.extensions.get(ANONYMOUS_EXTENSION):
        request.headers["Authorization"] = f"Bearer {token}"


def _slug_of(body: bytes) -> str | None:
    try:
        parsed: object = json.loads(body)
    except ValueError:
        return None
    slug = (as_dict(parsed) or {}).get("error")
    return slug if isinstance(slug, str) else None


def _failure_error(
    request: httpx.Request, retry_class: RetryClass, failure: httpx.TransportError
) -> NetworkError | OutcomeUnknownError:
    reason = type(failure).__name__
    path = request.url.path
    if retry_class is RetryClass.NEVER and not isinstance(
        failure, (httpx.ConnectError, httpx.ConnectTimeout)
    ):
        which = "claim" if path.endswith("/claim") else "rotate"
        return OutcomeUnknownError(
            f"No response arrived for {request.method} {_label(request)} ({reason}).",
            code="outcome_unknown",
            hint=_UNKNOWN_HINTS.get(which),
        )
    return NetworkError(
        f"Could not reach the Hushscript API: {request.method} {_label(request)} ({reason})."
    )


def _outcome_of(response: httpx.Response, retry_class: RetryClass) -> Outcome:
    slug = None
    if retry_class is RetryClass.CREATE and response.status_code == TOO_MANY_REQUESTS:
        slug = _slug_of(response.read())
    return Outcome(
        status=response.status_code,
        retry_after=parse_retry_after(response.headers.get("retry-after")),
        slug=slug,
    )


class _Attempt:
    """The bookkeeping shared by the sync and async transports."""

    def __init__(self, request: httpx.Request, settings: TransportSettings) -> None:
        self.request = request
        self.settings = settings
        self.retry_class = _retry_class(request)
        self.label = _label(request)
        self.number = 0
        self.started = settings.clock.now()
        _authorize(request, settings)

    def begin(self) -> None:
        self.started = self.settings.clock.now()

    def judge(self, outcome: Outcome) -> Decision:
        decision = decide(
            self.retry_class, self.number, self.settings.max_retries, outcome, self.settings.rng
        )
        elapsed = (self.settings.clock.now() - self.started) * 1000
        self.settings.log.attempt(
            self.request.method,
            self.label,
            outcome.status,
            self.number + 1,
            elapsed,
            decision.delay if decision.retry else None,
        )
        self.number += 1
        return decision


class RetryingTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport, settings: TransportSettings) -> None:
        self._inner = inner
        self._settings = settings

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        attempt = _Attempt(request, self._settings)
        while True:
            attempt.begin()
            try:
                response = self._inner.handle_request(request)
            except httpx.TransportError as failure:
                decision = attempt.judge(Outcome(failure=failure))
                if not decision.retry:
                    raise _failure_error(request, attempt.retry_class, failure) from failure
            else:
                decision = attempt.judge(_outcome_of(response, attempt.retry_class))
                if not decision.retry:
                    return response
                response.close()
            self._settings.clock.sleep(decision.delay)

    def close(self) -> None:
        self._inner.close()


class AsyncRetryingTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport, settings: TransportSettings) -> None:
        self._inner = inner
        self._settings = settings

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        attempt = _Attempt(request, self._settings)
        while True:
            attempt.begin()
            try:
                response = await self._inner.handle_async_request(request)
            except httpx.TransportError as failure:
                decision = attempt.judge(Outcome(failure=failure))
                if not decision.retry:
                    raise _failure_error(request, attempt.retry_class, failure) from failure
            else:
                if (
                    attempt.retry_class is RetryClass.CREATE
                    and response.status_code == TOO_MANY_REQUESTS
                ):
                    await response.aread()
                decision = attempt.judge(_outcome_of(response, attempt.retry_class))
                if not decision.retry:
                    return response
                await response.aclose()
            await self._settings.clock.asleep(decision.delay)

    async def aclose(self) -> None:
        await self._inner.aclose()
