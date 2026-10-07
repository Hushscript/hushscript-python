from __future__ import annotations

from typing import TYPE_CHECKING, Final

from hushscript._errors import JobFailedError, UploadError, WaitTimeoutError
from hushscript._models import Job, ProcessingProgress, to_transcript
from hushscript._response import parsed

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import httpx

    from hushscript._clock import Clock
    from hushscript._models import Progress, Transcript
    from hushscript._redact import Credentials

FIRST_POLL_DELAY: Final = 5.0
POLL_GROWTH: Final = 1.5
MAX_POLL_DELAY: Final = 15.0
DEFAULT_WAIT_TIMEOUT: Final = 3600.0
TERMINAL: Final = frozenset({"done", "failed"})


def next_delay(delay: float) -> float:
    """Spec 8.6: 5 s, times 1.5 each poll, to a 15 s ceiling (the app's cadence)."""
    return min(delay * POLL_GROWTH, MAX_POLL_DELAY)


def job_failed(job: Job) -> JobFailedError:
    return JobFailedError(
        "The transcription failed.",
        job_id=job.id,
        error=job.error,
        failure_kind=job.failure_kind,
    )


def timed_out(wait_timeout: float, token: str | None) -> WaitTimeoutError:
    return WaitTimeoutError(
        f"The job was still running after {wait_timeout:g} s. It keeps running on the server.",
        resume_token=token,
    )


def missing_transcript(job: Job) -> UploadError:
    return UploadError(f"Job {job.id} is done but names no transcript.", code="transcript_missing")


def wait_for_job(  # the poll loop, with every dependency passed in
    get_job: Callable[[], Job],
    clock: Clock,
    wait_timeout: float,
    on_progress: Callable[[Progress], None] | None = None,
    token: str | None = None,
    first: Job | None = None,
) -> Job:
    """Polls until `done` or `failed` and returns the job, or raises WaitTimeoutError. `first` is
    a job read a moment ago, which stands in for the first poll."""
    started = clock.now()
    delay = FIRST_POLL_DELAY
    while True:
        job = first or get_job()
        first = None
        if job.state in TERMINAL:
            return job
        if on_progress is not None:
            on_progress(ProcessingProgress(state=job.state))
        remaining = started + wait_timeout - clock.now()
        if remaining <= 0:
            raise timed_out(wait_timeout, token)
        clock.sleep(min(delay, remaining))
        delay = next_delay(delay)


async def await_job(  # the same loop on the event loop
    get_job: Callable[[], Awaitable[Job]],
    clock: Clock,
    wait_timeout: float,
    on_progress: Callable[[Progress], None] | None = None,
    token: str | None = None,
    first: Job | None = None,
) -> Job:
    started = clock.now()
    delay = FIRST_POLL_DELAY
    while True:
        job = first or await get_job()
        first = None
        if job.state in TERMINAL:
            return job
        if on_progress is not None:
            on_progress(ProcessingProgress(state=job.state))
        remaining = started + wait_timeout - clock.now()
        if remaining <= 0:
            raise timed_out(wait_timeout, token)
        await clock.asleep(min(delay, remaining))
        delay = next_delay(delay)


def job_from(response: httpx.Response, credentials: Credentials) -> Job:
    return parsed(response, credentials, Job.from_body)


def finish(job: Job) -> str:
    """The transcript id of a finished job; a failed job raises JobFailedError."""
    if job.state == "failed":
        raise job_failed(job)
    if job.transcript_id is None:
        raise missing_transcript(job)
    return job.transcript_id


def transcript_of(response: httpx.Response, credentials: Credentials) -> Transcript:
    return parsed(response, credentials, to_transcript)
