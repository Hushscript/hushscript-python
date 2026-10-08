from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, cast

import httpx

from ._config import PART_TIMEOUT
from ._errors import (
    HushscriptError,
    NetworkError,
    OutcomeUnknownError,
    parse_retry_after,
    unexpected_error,
)
from ._guard import generated_parser, unusable_answer
from ._json import as_dict, loads
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
    from ._pacing import TokenBucket
    from ._redact import Credentials

LABEL_EXTENSION: Final = "hushscript_label"
CLASS_EXTENSION: Final = "hushscript_class"
ANONYMOUS_EXTENSION: Final = "hushscript_anonymous"
# Set on a part PUT: the transport still guards the attempt but leaves the response body unread,
# so the caller decides whether to read it (a large download must not be buffered whole).
STREAM_EXTENSION: Final = "hushscript_stream"
IDEMPOTENCY_FIELD: Final = "idempotency_key"
PURCHASE_PATH: Final = "/v1/billing/purchase"

_PHASES: Final = ("connect", "read", "write", "pool")
# Classes whose decision needs no response body, so the body may be left for the caller.
_STREAMABLE: Final = frozenset({RetryClass.SAFE, RetryClass.PART})

# Spec 7.4. A lost signup has no hint in v0.1.
UNKNOWN_HINTS: Final = {
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
    bucket: TokenBucket | None = None
    """Paces `POST /v1/uploads` for the client (spec 7.5), keyed or not."""

    @property
    def ceiling(self) -> float:
        """The longest deadline any request can ask for: a per-request timeout above the
        configured one (an upload part's, `hs.api.with_timeout`) is honored up to this bound."""
        return max(self.timeout, PART_TIMEOUT)


def _same_origin(url: httpx.URL, other: httpx.URL) -> bool:
    return (url.scheme, url.host, url.port) == (other.scheme, other.host, other.port)


def _label(request: httpx.Request) -> str:
    label = request.extensions.get(LABEL_EXTENSION)
    return label if isinstance(label, str) else request.url.path


def _idempotency_key(request: httpx.Request) -> str | None:
    try:
        parsed: object = loads(request.content)
    except (ValueError, RecursionError, httpx.RequestNotRead):
        return None
    key = (as_dict(parsed) or {}).get(IDEMPOTENCY_FIELD)
    return key if isinstance(key, str) and key else None


def _slug_of(body: bytes) -> str | None:
    try:
        parsed: object = loads(body)
    except (ValueError, RecursionError):
        return None
    slug = (as_dict(parsed) or {}).get("error")
    return slug if isinstance(slug, str) else None


def release(request: httpx.Request) -> None:
    """Lets go of the part's bytes. httpx ties a response to its request in a reference cycle that
    only the garbage collector clears, which would keep every finished part alive for a while."""
    request.stream = httpx.ByteStream(b"")
    request._content = b""  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]  # httpx cached the body


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
        # R61: every error after a purchase went out carries its key, whoever made the request.
        # Only that request's body is read for it: a part's body is megabytes of media.
        self.purchase_key = _idempotency_key(request) if on_base and path == PURCHASE_PATH else None
        if self.retry_class is RetryClass.CREATE and _idempotency_key(request) is None:
            # Only a keyed create is a safe replay; without a key it is any other mutation.
            self.retry_class = RetryClass.MUTATE
        self.stream = (
            bool(request.extensions.get(STREAM_EXTENSION)) and self.retry_class in _STREAMABLE
        )
        self.label = _label(request)
        self.number = 0
        self.limited: dict[str, int] = {}
        self.started = settings.clock.now()
        self.budget = settings.timeout
        self.deadline = self.started + self.budget
        self.body: _WrittenBody | None = None
        self.answered = False
        self.phases: dict[str, float | None] = {}
        self._track_body()

    def _authorize(self) -> None:
        credentials = self.settings.credentials
        token = None if credentials is None else credentials.token
        if not self.on_base or self.request.extensions.get(ANONYMOUS_EXTENSION):
            return
        if token is not None:
            self.request.headers["Authorization"] = f"Bearer {token}"
        else:
            # A token that was unset since an earlier attempt must not ride along on this one.
            self.request.headers.pop("Authorization", None)

    def _track_body(self) -> None:
        if self.retry_class is RetryClass.NEVER:
            self.body = _WrittenBody(self.request.stream)
            self.request.stream = self.body
        configured = self.request.extensions.get("timeout")
        if isinstance(configured, dict):
            known = cast("dict[str, float | None]", configured)
            self.phases = {phase: known.get(phase) for phase in _PHASES}
            asked = [limit for limit in self.phases.values() if limit is not None]
            if asked:
                self.budget = min(self.settings.ceiling, max(self.settings.timeout, *asked))

    def begin(self) -> None:
        # The token is read per attempt, after any pacing or backoff sleep, so a rotation applies
        # to a request that was queued behind it (spec 7.4, R44).
        self._authorize()
        self.started = self.settings.clock.now()
        self.deadline = self.started + self.budget
        self.answered = False
        if self.body is not None:
            self.body.done = False
        self.tighten()

    def pace(self) -> float:
        """Seconds to wait before an upload create may go out (spec 7.5); every attempt takes a
        token, whatever its retry class, a retry included."""
        bucket = self.settings.bucket
        if bucket is None or not self.on_base or self.request.method != "POST":
            return 0.0
        if (
            self.request.url.path.removeprefix(self.settings.base_url.path.rstrip("/"))
            != "/v1/uploads"
        ):
            return 0.0
        return bucket.reserve()

    def remaining(self) -> float:
        return self.deadline - self.settings.clock.now()

    def tighten(self) -> None:
        """Holds the attempt to one overall deadline of `budget` seconds (spec 3 and 7.1).

        httpx's own timeout is per phase. Before the request and before every body chunk the
        remaining time is computed and the phase timeouts are cut to it; with none left the attempt
        fails like any other timeout.
        """
        remaining = self.remaining()
        if remaining <= 0:
            raise httpx.ReadTimeout(
                f"the request took longer than {self.budget:g} s", request=self.request
            )
        if self.phases:
            self.request.extensions["timeout"] = {
                phase: remaining if limit is None else min(limit, remaining)
                for phase, limit in self.phases.items()
            }

    def read(self, response: httpx.Response) -> None:
        response.stream = _DeadlineBody(response.stream, self)

    def stamp(self, error: HushscriptError) -> None:
        if self.purchase_key is not None and error.idempotency_key is None:
            error.idempotency_key = self.purchase_key

    def unusable(self, response: httpx.Response) -> HushscriptError | None:
        """For a call made through a generated function (`hs.api`): the error for an answer its
        parser cannot read, which would otherwise leave as a bare `JSONDecodeError`, `KeyError` or
        `TypeError` (R61)."""
        parse = None if self.stream else generated_parser()
        if parse is None:
            return None
        return unusable_answer(parse, response, self.settings.credentials)

    def sent(self) -> bool:
        """The body was fully written, or an answer came, which a transport that never reads the
        body proves just as well."""
        return self.answered or (self.body is not None and self.body.done)

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

    def failure_error(self, failure: httpx.RequestError) -> NetworkError | OutcomeUnknownError:
        reason = type(failure).__name__
        where = f"{self.request.method} {self.label}"
        if self.retry_class is RetryClass.NEVER and not is_not_sent(failure):
            return OutcomeUnknownError(
                f"No response arrived for {where} ({reason}).",
                code="outcome_unknown",
                hint=UNKNOWN_HINTS.get(self.route or ""),
            )
        return NetworkError(f"Could not reach the Hushscript API: {where} ({reason}).")

    def unexpected(self, failure: Exception) -> HushscriptError:
        """Spec 9.2 and R61: a failure of the SDK's own. A claim, rotation or signup answer lost
        this way after the request went out is as lost as one that never came (spec 7.4); one
        before it was sent lost nothing."""
        error = unexpected_error(failure, self.settings.credentials)
        if self.retry_class is not RetryClass.NEVER or not self.sent():
            return error
        unknown = OutcomeUnknownError(
            f"The answer to {self.request.method} {self.label} could not be used "
            f"({type(failure).__name__}).",
            code="outcome_unknown",
            hint=UNKNOWN_HINTS.get(self.route or ""),
        )
        unknown.__cause__ = error.__cause__
        return unknown

    def note_cancellation(self, cancelled: asyncio.CancelledError) -> None:
        """Spec 7.4: a cancel after a claim, rotate or signup body was written leaves the outcome
        unknown. The cancellation itself must reach asyncio untouched (timeouts and task groups
        depend on it), so the outcome rides along as a note."""
        if not self.sent():
            return
        hint = UNKNOWN_HINTS.get(self.route or "")
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
        del request
        try:
            return self._run(attempt)
        except BaseException as error:
            if isinstance(error, HushscriptError):
                attempt.stamp(error)
            if attempt.retry_class is RetryClass.PART:
                release(attempt.request)
            raise

    def _run(self, attempt: _Attempt) -> httpx.Response:
        while True:
            if (paced := attempt.pace()) > 0:
                self._settings.clock.sleep(paced)
            attempt.begin()
            decision, response = self._once(attempt)
            if response is not None:
                if not decision.retry:
                    if (unusable := attempt.unusable(response)) is not None:
                        response.close()
                        raise unusable
                    return response
                response.close()
            self._settings.clock.sleep(decision.delay)

    def _once(self, attempt: _Attempt) -> tuple[Decision, httpx.Response | None]:
        """One attempt: what to do next and the response, if one came. Nothing but an SDK error
        leaves it (R61)."""
        unexpected: HushscriptError | None = None
        try:
            try:
                response = self._send(attempt)
            except httpx.RequestError as failure:
                decision = attempt.judge(Outcome(failure=failure))
                if not decision.retry:
                    raise attempt.failure_error(failure) from failure
                return decision, None
            try:
                return attempt.judge(attempt.outcome_of(response)), response
            except BaseException:
                response.close()
                raise
        except HushscriptError:
            raise
        except Exception as failure:  # noqa: BLE001  # R61: nothing but an SDK error leaves
            unexpected = attempt.unexpected(failure)
        raise unexpected

    def _send(self, attempt: _Attempt) -> httpx.Response:
        response = self._inner.handle_request(attempt.request)
        attempt.answered = True
        try:
            attempt.read(response)
            if not attempt.stream:
                response.read()
        except BaseException:
            response.close()
            raise
        return response

    def close(self) -> None:
        self._inner.close()


class AsyncRetryingTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport, settings: TransportSettings) -> None:
        self._inner = inner
        self._settings = settings

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        attempt = _Attempt(request, self._settings)
        del request
        try:
            return await self._run(attempt)
        except BaseException as error:
            if isinstance(error, HushscriptError):
                attempt.stamp(error)
            if attempt.retry_class is RetryClass.PART:
                release(attempt.request)
            raise

    async def _run(self, attempt: _Attempt) -> httpx.Response:
        while True:
            if (paced := attempt.pace()) > 0:
                await self._settings.clock.asleep(paced)
            attempt.begin()
            decision, response = await self._once(attempt)
            if response is not None:
                if not decision.retry:
                    if (unusable := attempt.unusable(response)) is not None:
                        await response.aclose()
                        raise unusable
                    return response
                await response.aclose()
            await self._settings.clock.asleep(decision.delay)

    async def _once(self, attempt: _Attempt) -> tuple[Decision, httpx.Response | None]:
        """One attempt: what to do next and the response, if one came. Nothing but an SDK error
        leaves it (R61); a cancellation passes through, with the note a lost secret needs."""
        unexpected: HushscriptError | None = None
        try:
            try:
                response = await self._send(attempt)
            except httpx.RequestError as failure:
                decision = attempt.judge(Outcome(failure=failure))
                if not decision.retry:
                    raise attempt.failure_error(failure) from failure
                return decision, None
            except asyncio.CancelledError as cancelled:
                attempt.note_cancellation(cancelled)
                raise
            try:
                return attempt.judge(attempt.outcome_of(response)), response
            except BaseException:
                await response.aclose()
                raise
        except HushscriptError:
            raise
        except Exception as failure:  # noqa: BLE001  # R61: nothing but an SDK error leaves
            unexpected = attempt.unexpected(failure)
        raise unexpected

    async def _send(self, attempt: _Attempt) -> httpx.Response:
        """One attempt, held to its deadline even while blocked on the network. Only the expiry of
        this timeout becomes a failure; a cancellation from the caller passes through."""
        try:
            async with asyncio.timeout(max(attempt.remaining(), 0.0)):
                response = await self._inner.handle_async_request(attempt.request)
                attempt.answered = True
                try:
                    attempt.read(response)
                    if not attempt.stream:
                        await response.aread()
                except BaseException:
                    await response.aclose()
                    raise
        except TimeoutError as expired:
            raise httpx.ReadTimeout(
                f"the request took longer than {attempt.budget:g} s", request=attempt.request
            ) from expired
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()
