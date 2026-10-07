from __future__ import annotations

import random
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx

from hushscript._http import (
    AsyncRetryingTransport,
    RetryingTransport,
    TransportSettings,
)
from hushscript._log import RequestLog
from hushscript._redact import Credentials

if TYPE_CHECKING:
    import threading
    from collections.abc import AsyncIterator, Iterator, Sequence

BASE_URL = "http://127.0.0.1:4010"
# A callable builds a fresh response per call, which a response with a stream needs: a stream can
# be read once.
Step = httpx.Response | Exception | Callable[[], httpx.Response]


class FakeClock:
    def __init__(self) -> None:
        self.time = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.time += seconds

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        if not stop.is_set():
            self.sleep(seconds)
        return stop.is_set()

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


class Script:
    """Answers each request with the next step; an Exception step is raised as a failure."""

    def __init__(self, steps: Sequence[Step]) -> None:
        self.steps = list(steps)
        self.requests: list[httpx.Request] = []

    def _next(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step = self.steps.pop(0) if len(self.steps) > 1 else self.steps[0]
        if isinstance(step, Exception):
            raise step
        return step() if callable(step) else step

    def sync(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._next)

    def asynchronous(self) -> httpx.MockTransport:
        async def handler(request: httpx.Request) -> httpx.Response:
            return self._next(request)

        return httpx.MockTransport(handler)

    @property
    def calls(self) -> int:
        return len(self.requests)


def settings_for(
    clock: FakeClock,
    *,
    max_retries: int = 3,
    token: str | None = None,
    level: str = "off",
    base_url: str = BASE_URL,
    timeout: float = 60.0,
) -> TransportSettings:
    return TransportSettings(
        clock=clock,
        log=RequestLog(level),
        credentials=Credentials(token),
        max_retries=max_retries,
        base_url=httpx.URL(base_url),
        timeout=timeout,
        rng=random.Random(7),  # noqa: S311  # deterministic jitter for tests
    )


def sync_client(
    script: Script,
    clock: FakeClock,
    *,
    max_retries: int = 3,
    token: str | None = None,
    level: str = "off",
    base_url: str = BASE_URL,
    timeout: float = 60.0,
) -> httpx.Client:
    settings = settings_for(
        clock, max_retries=max_retries, token=token, level=level, base_url=base_url, timeout=timeout
    )
    return httpx.Client(
        base_url=base_url,
        transport=RetryingTransport(script.sync(), settings),
    )


def async_client(
    script: Script,
    clock: FakeClock,
    *,
    max_retries: int = 3,
    token: str | None = None,
    level: str = "off",
    base_url: str = BASE_URL,
    timeout: float = 60.0,
) -> httpx.AsyncClient:
    settings = settings_for(
        clock, max_retries=max_retries, token=token, level=level, base_url=base_url, timeout=timeout
    )
    return httpx.AsyncClient(
        base_url=base_url,
        transport=AsyncRetryingTransport(script.asynchronous(), settings),
    )


def reply(
    status: int,
    body: object = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    if body is None:
        return httpx.Response(status, headers=headers, text="status text")
    return httpx.Response(status, json=body, headers=headers)


def error_body(slug: str, code: int, **extra: object) -> dict[str, object]:
    return {"error": slug, "code": code, **extra}


class FailingBody(httpx.SyncByteStream, httpx.AsyncByteStream):
    """A response body that breaks after its chunks, as a connection reset or a read timeout does
    once the headers have arrived."""

    def __init__(self, failure: Exception, chunks: tuple[bytes, ...] = ()) -> None:
        self.failure = failure
        self.chunks = chunks

    def __iter__(self) -> Iterator[bytes]:
        yield from self.chunks
        raise self.failure

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            yield chunk
        raise self.failure


def failing_body(
    failure: Exception, status: int = 200, chunks: tuple[bytes, ...] = ()
) -> Callable[[], httpx.Response]:
    """A step whose headers arrive and whose body then fails, afresh on every call."""

    def build() -> httpx.Response:
        return httpx.Response(status, stream=FailingBody(failure, chunks))

    return build


class SlowBody(httpx.SyncByteStream, httpx.AsyncByteStream):
    """A body that delivers `count` chunks, each one `seconds` of clock time after the last."""

    def __init__(self, clock: FakeClock, seconds: float, count: int) -> None:
        self.clock = clock
        self.seconds = seconds
        self.count = count

    def __iter__(self) -> Iterator[bytes]:
        for _ in range(self.count):
            self.clock.time += self.seconds
            yield b"x"

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for _ in range(self.count):
            self.clock.time += self.seconds
            yield b"x"


OPTIONS: dict[str, object] = {
    "language_code": None,
    "speaker_detection": True,
    "medical_mode": False,
    "multichannel": False,
    "translation_targets": [],
    "keyterms": False,
    "prompt": False,
    "auto_generate_insights": None,
}


def job_body(job_id: str, state: str, **fields: object) -> dict[str, object]:
    """A job as `GET /v1/jobs/{id}` returns it, every field present."""
    return {
        "id": job_id,
        "state": state,
        "mode": "standard",
        "declared_seconds": 24,
        "verified_seconds": None,
        "actual_seconds": None,
        "billable_seconds": 0,
        "error": None,
        "failure_kind": None,
        "retry_of": None,
        "created_at": 1_700_000_000,
        "transcript_id": None,
        "private_result_expires_at": None,
        "private_result_available": False,
        "options": OPTIONS,
        **fields,
    }


def transcript_body(transcript_id: str = "tr_1", **fields: object) -> dict[str, object]:
    """A transcript as `GET /v1/transcripts/{id}` returns it, every field present."""
    return {
        "id": transcript_id,
        "title": "Weekly sync",
        "language_detected": "en",
        "duration_seconds": 24,
        "speaker_names": {},
        "tags": [],
        "created_at": 1_700_000_000,
        "updated_at": 1_700_000_100,
        "auto_delete_at": None,
        "edited": False,
        "matter_code": None,
        "client_code": None,
        "body": {
            "version": 1,
            "original": {
                "utterances": [{"speaker": "A", "start_ms": 0, "end_ms": 900, "text": "Hi."}]
            },
            "translations": {},
        },
        **fields,
    }


def account_body(**fields: object) -> dict[str, object]:
    return {
        "balance_seconds": 36000,
        "held_seconds": 0,
        "credits_expire_at": None,
        "card_on_file": True,
        "data_region": "eu",
        "limits": {
            "max_daily_seconds": 36000,
            "max_active_jobs": 50,
            "active_jobs": 0,
            "used_today_seconds": 0,
        },
        **fields,
    }
