from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, cast

import httpx

from ._errors import NetworkError, OutcomeUnknownError, parse_retry_after
from ._json import as_dict
from ._retry import (
    CLAIM,
    ROTATE,
    Decision,
    Outcome,
    RetryClass,
    classify,
    create_limit_kind,
    decide,
    is_not_sent,
    unrecoverable_route,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Iterable, Iterator

    from ._clock import Clock
    from ._log import RequestLog
    from ._redact import Credentials

LABEL_EXTENSION: Final = "hushscript_label"
CLASS_EXTENSION: Final = "hushscript_class"
ANONYMOUS_EXTENSION: Final = "hushscript_anonymous"

_PHASES: Final = ("connect", "read", "write", "pool")

# Spec 7.4. A lost signup has no hint in v0.1.
_UNKNOWN_HINTS: Final = {
    CLAIM: (
        "The claim may have succeeded. Retrying will fail with agent_claim_invalid. "
        "If you have no token, contact support with the signup id."
    ),
    ROTATE: (
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
    base_url: httpx.URL
    timeout: float
    rng: random.Random = field(default_factory=random.SystemRandom)


def _same_origin(url: httpx.URL, other: httpx.URL) -> bool:
    return (url.scheme, url.host, url.port) == (other.scheme, other.host, other.port)


def _label(request: httpx.Request) -> str:
    label = request.extensions.get(LABEL_EXTENSION)
    return label if isinstance(label, str) else request.url.path


def _slug_of(body: bytes) -> str | None:
    try:
        parsed: object = json.loads(body)
    except ValueError:
        return None
    slug = (as_dict(parsed) or {}).get("error")
    return slug if isinstance(slug, str) else None


class _WrittenBody(httpx.SyncByteStream, httpx.AsyncByteStream):
    """Passes a request body through and notes when the last chunk has been handed to the socket."""

    def __init__(self, inner: httpx.SyncByteStream | httpx.AsyncByteStream) -> None:
        self._inner = inner
        self.done = False

    def __iter__(self) -> Iterator[bytes]:
        yield from cast("Iterable[bytes]", self._inner)
        self.done = True

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in cast("AsyncIterable[bytes]", self._inner):
            yield chunk
        self.done = True

    def close(self) -> None:
        cast("httpx.SyncByteStream", self._inner).close()

    async def aclose(self) -> None:
        await cast("httpx.AsyncByteStream", self._inner).aclose()


class _DeadlineBody(httpx.SyncByteStream, httpx.AsyncByteStream):
    """Reads a response body chunk by chunk, holding every chunk to the attempt's deadline."""

    def __init__(
        self, inner: httpx.SyncByteStream | httpx.AsyncByteStream, attempt: _Attempt
    ) -> None:
        self._inner = inner
        self._attempt = attempt

    def __iter__(self) -> Iterator[bytes]:
        chunks = iter(cast("Iterable[bytes]", self._inner))
        while True:
            self._attempt.tighten()
            try:
                chunk = next(chunks)
            except StopIteration:
                return
            yield chunk

    async def __aiter__(self) -> AsyncIterator[bytes]:
        chunks = aiter(cast("AsyncIterable[bytes]", self._inner))
        while True:
            self._attempt.tighten()
            try:
                chunk = await anext(chunks)
            except StopAsyncIteration:
                return
            yield chunk

    def close(self) -> None:
        cast("httpx.SyncByteStream", self._inner).close()

    async def aclose(self) -> None:
        await cast("httpx.AsyncByteStream", self._inner).aclose()


class _Attempt:
    """The bookkeeping shared by the sync and async transports."""

    def __init__(self, request: httpx.Request, settings: TransportSettings) -> None:
        self.request = request
        self.settings = settings
        on_base = _same_origin(request.url, settings.base_url)
        # Spec 7.4: the class comes from the method and the path relative to the base URL. A
        # request to any other host (a signed R2 URL) matches no API route; only it may carry a
        # class of its own.
        path = request.url.path.removeprefix(settings.base_url.path.rstrip("/")) if on_base else ""
        self.on_base = on_base
        self.route = unrecoverable_route(request.method, path)
        override = None if on_base else request.extensions.get(CLASS_EXTENSION)
        self.retry_class = (
            override if isinstance(override, RetryClass) else classify(request.method, path)
        )
        self.label = _label(request)
        self.number = 0
        self.limited: dict[str, int] = {}
        self.started = settings.clock.now()
        self.deadline = self.started + settings.timeout
        self.body: _WrittenBody | None = None
        self.phases: dict[str, float | None] = {}
        self._authorize()
        self._track_body()

    def _authorize(self) -> None:
        credentials = self.settings.credentials
        token = None if credentials is None else credentials.token
        if (
            token is not None
            and self.on_base
            and not self.request.extensions.get(ANONYMOUS_EXTENSION)
        ):
            self.request.headers["Authorization"] = f"Bearer {token}"

    def _track_body(self) -> None:
        if self.retry_class is RetryClass.NEVER:
            self.body = _WrittenBody(self.request.stream)
            self.request.stream = self.body
        configured = self.request.extensions.get("timeout")
        if isinstance(configured, dict):
            known = cast("dict[str, float | None]", configured)
            self.phases = {phase: known.get(phase) for phase in _PHASES}

    def begin(self) -> None:
        self.started = self.settings.clock.now()
        self.deadline = self.started + self.settings.timeout
        if self.body is not None:
            self.body.done = False
        self.tighten()

    def tighten(self) -> None:
        """Holds the attempt to one overall deadline of `timeout` seconds (spec 3 and 7.1).

        httpx's own timeout is per phase. Before the request and before every body chunk the
        remaining time is computed and the phase timeouts are cut to it; with none left the attempt
        fails like any other timeout.
        """
        remaining = self.deadline - self.settings.clock.now()
        if remaining <= 0:
            raise httpx.ReadTimeout(
                f"the request took longer than {self.settings.timeout:g} s", request=self.request
            )
        if self.phases:
            self.request.extensions["timeout"] = {
                phase: remaining if limit is None else min(limit, remaining)
                for phase, limit in self.phases.items()
            }

    def read(self, response: httpx.Response) -> None:
        response.stream = _DeadlineBody(response.stream, self)

    def sent(self) -> bool:
        return self.body is not None and self.body.done

    def judge(self, outcome: Outcome) -> Decision:
        kind = create_limit_kind(self.retry_class, outcome)
        decision = decide(
            self.retry_class,
            self.number,
            self.settings.max_retries,
            outcome,
            self.settings.rng,
            own_429=None if kind is None else self.limited.get(kind, 0),
        )
        if kind is not None and decision.retry:
            self.limited[kind] = self.limited.get(kind, 0) + 1
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

    def outcome_of(self, response: httpx.Response) -> Outcome:
        slug = None
        if create_limit_kind(self.retry_class, Outcome(status=response.status_code)) is not None:
            slug = _slug_of(response.content)
        return Outcome(
            status=response.status_code,
            retry_after=parse_retry_after(response.headers.get("retry-after")),
            slug=slug,
        )

    def failure_error(self, failure: httpx.TransportError) -> NetworkError | OutcomeUnknownError:
        reason = type(failure).__name__
        where = f"{self.request.method} {self.label}"
        if self.retry_class is RetryClass.NEVER and not is_not_sent(failure):
            return OutcomeUnknownError(
                f"No response arrived for {where} ({reason}).",
                code="outcome_unknown",
                hint=_UNKNOWN_HINTS.get(self.route or ""),
            )
        return NetworkError(f"Could not reach the Hushscript API: {where} ({reason}).")

    def note_cancellation(self, cancelled: asyncio.CancelledError) -> None:
        """Spec 7.4: a cancel after a claim, rotate or signup body was written leaves the outcome
        unknown. The cancellation itself must reach asyncio untouched (timeouts and task groups
        depend on it), so the outcome rides along as a note."""
        if not self.sent():
            return
        hint = _UNKNOWN_HINTS.get(self.route or "")
        text = (
            f"Cancelled after {self.request.method} {self.label} was sent: its outcome is unknown."
        )
        cancelled.add_note(f"{text} {hint}" if hint else text)


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
                try:
                    attempt.read(response)
                    response.read()
                except BaseException:
                    response.close()
                    raise
            except httpx.TransportError as failure:
                decision = attempt.judge(Outcome(failure=failure))
                if not decision.retry:
                    raise attempt.failure_error(failure) from failure
            else:
                decision = attempt.judge(attempt.outcome_of(response))
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
                try:
                    attempt.read(response)
                    await response.aread()
                except BaseException:
                    await response.aclose()
                    raise
            except httpx.TransportError as failure:
                decision = attempt.judge(Outcome(failure=failure))
                if not decision.retry:
                    raise attempt.failure_error(failure) from failure
            except asyncio.CancelledError as cancelled:
                attempt.note_cancellation(cancelled)
                raise
            else:
                decision = attempt.judge(attempt.outcome_of(response))
                if not decision.retry:
                    return response
                await response.aclose()
            await self._settings.clock.asleep(decision.delay)

    async def aclose(self) -> None:
        await self._inner.aclose()
