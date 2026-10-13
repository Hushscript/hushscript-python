from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, TypeVar

from hushscript._errors import (
    HushscriptError,
    NotFoundError,
    add_note,
    raise_for_response,
    unexpected_error,
)
from hushscript._models import Job, UploadingProgress
from hushscript._response import json_body, parsed

from .heartbeat import Heartbeat
from .preflight import Media, Options, check_account, check_media, create_body
from .resume import (
    ResumeState,
    decode_token,
    early_source,
    encode_token,
    file_required,
    job_missing,
    late_source,
)
from .segment import segment
from .source import FileInput, Source, make_source
from .upload import SyncUploader, parse_created, stream_size_mismatch
from .wait import finish, job_from, transcript_of, wait_for_job

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from hushscript._models import Progress
    from hushscript._redact import Credentials
    from hushscript.transcript import Transcript

    from .session import SyncSession
    from .upload import Created

UPLOADING: Final = "uploading"
RESUME_NOTE: Final = "The job exists on the server. Resume it with this token: "
SENT_NOTE: Final = "The create request was sent, so the job may exist. Idempotency key: "
T = TypeVar("T")


@dataclass(slots=True)
class Tracker:
    """What an error raised after the create was sent has to carry (spec 7.3)."""

    key: str
    token: str | None = None
    sent: bool = False
    """True from the moment the create goes out: the server may have committed it."""
    callers: list[BaseException] = field(default_factory=list)
    """What the caller's own callbacks raised: those pass through unchanged (R63)."""
    credentials: Credentials | None = None
    """What an unexpected failure's cause is redacted with."""

    def note(self) -> str:
        if self.token is None:
            return f"{SENT_NOTE}{self.key}"
        return f"{RESUME_NOTE}{self.token} (idempotency key {self.key})"

    def from_caller(self, failure: BaseException) -> bool:
        return any(failure is raised for raised in self.callers)


def note_interrupt(tracker: Tracker, interrupted: BaseException) -> None:
    """Spec 7.4 and R26: an interrupt is never converted (asyncio.timeout and task groups depend on
    it); once the create is out, the way back to the job rides along as a note."""
    if tracker.sent:
        add_note(interrupted, tracker.note())


def annotate(tracker: Tracker, failure: Exception) -> HushscriptError:
    """What an error raised after the create went out turns into. Called from the handler of
    `failure`: what passes through unchanged is re-raised from here, and the error returned is for
    the caller to raise once its handler has ended, so the unredacted original is not left on the
    error's `__context__`."""
    # R63 first: what the caller's own callbacks raised, an SDK error among it (a nested `buy()`
    # failing with its own key), reaches the caller as it is.
    if tracker.from_caller(failure):
        raise failure
    if isinstance(failure, HushscriptError):
        failure.idempotency_key = tracker.key
        if tracker.token is not None and failure.resume_token is None:
            failure.resume_token = tracker.token
        raise failure
    # R61: once the create is out nothing but an SDK error leaves.
    if not tracker.sent:
        raise failure
    failed = unexpected_error(failure, tracker.credentials, sent=True)
    failed.idempotency_key = tracker.key
    failed.resume_token = tracker.token
    return failed


def annotated(tracker: Tracker, run: Callable[[], T]) -> T:
    """`run()`, where every failure after the create went out is an SDK error that carries the key
    and the token (spec 7.3)."""
    try:
        return run()
    except (asyncio.CancelledError, KeyboardInterrupt) as interrupted:
        note_interrupt(tracker, interrupted)
        raise
    except Exception as failure:  # noqa: BLE001  # R61: nothing but an SDK error leaves
        failed = annotate(tracker, failure)
    raise failed


def replay_body(state: ResumeState) -> Mapping[str, object]:
    return {
        "size_bytes": state.size,
        "duration_seconds": state.duration_seconds,
        "idempotency_key": state.idempotency_key,
    }


@dataclass(frozen=True, slots=True)
class Callbacks:
    on_progress: Callable[[Progress], None] | None = None
    on_resume_token: Callable[[str], None] | None = None
    raised: list[BaseException] = field(default_factory=list)
    """Whatever the callbacks raised, so the pipeline can tell it from a failure of its own."""

    def progress(self, event: Progress) -> None:
        if self.on_progress is not None:
            try:
                self.on_progress(event)
            except Exception as failure:
                self.raised.append(failure)
                raise

    def resume_token(self, token: str) -> None:
        if self.on_resume_token is not None:
            try:
                self.on_resume_token(token)
            except Exception as failure:
                self.raised.append(failure)
                raise


def percent(sent: int, total: int) -> int:
    return min(100, sent * 100 // total) if total else 100


def create(session: SyncSession, body: Mapping[str, object]) -> Created:
    """`POST /v1/uploads`; the transport paces it to the 4 per minute the API allows (spec 7.5)."""
    response = session.http.post("/v1/uploads", json=body)
    return parsed(response, session.credentials, parse_created)


def get_job(session: SyncSession, job_segment: str) -> Job:
    return job_from(session.http.get(f"/v1/jobs/{job_segment}"), session.credentials)


def wait_job(
    session: SyncSession,
    job_segment: str,
    wait_timeout: float,
    callbacks: Callbacks,
    token: str | None,
    first: Job | None = None,
) -> Job:
    return wait_for_job(
        lambda: get_job(session, job_segment),
        session.clock,
        wait_timeout,
        callbacks.progress,
        token,
        first,
    )


def fetch_transcript(session: SyncSession, job: Job) -> Transcript:
    transcript_id = finish(job)
    return transcript_of(
        session.http.get(f"/v1/transcripts/{segment(transcript_id)}"), session.credentials
    )


def _upload(
    session: SyncSession,
    created: Created,
    source: Source,
    concurrency: int,
    callbacks: Callbacks,
) -> None:
    job_path = f"/v1/uploads/{segment(created.job_id)}"
    uploader = SyncUploader(session, created.job_id, created.plan, source, concurrency)
    heartbeat = Heartbeat(session.clock, session.log)

    def ping() -> None:
        raise_for_response(
            session.http.post(f"{job_path}/heartbeat"), credentials=session.credentials
        )

    heartbeat.start(ping)
    try:
        total = source.size
        uploader.upload(
            lambda sent: callbacks.progress(UploadingProgress(percent(sent, total), sent, total)),
            heartbeat,
        )
        heartbeat.raise_if_failed()
        if not source.at_end():
            raise stream_size_mismatch()
        body = uploader.state.parts_body()
        response = (
            session.http.post(f"{job_path}/complete")
            if body is None
            else session.http.post(f"{job_path}/complete", json=body)
        )
        raise_for_response(response, credentials=session.credentials)
    finally:
        heartbeat.stop()


def _after_create(  # the upload, wait and fetch that follow a create, for a new call and a resume
    session: SyncSession,
    created: Created,
    tracker: Tracker,
    state: ResumeState,
    source: Source | None,
    options: Options,
    callbacks: Callbacks,
) -> Transcript:
    token = encode_token(
        ResumeState(created.job_id, state.idempotency_key, state.size, state.duration_seconds)
    )
    tracker.token = token
    callbacks.resume_token(token)
    if created.state == UPLOADING:
        if source is None:
            raise file_required()
        _upload(session, created, source, options.concurrency, callbacks)
    job = wait_job(session, segment(created.job_id), options.wait_timeout, callbacks, token)
    return fetch_transcript(session, job)


def run_transcribe(
    session: SyncSession,
    file: FileInput,
    options: Options,
    size: int | None,
    callbacks: Callbacks,
) -> Transcript:
    options.validate()
    source = make_source(file, size)
    media: Media = check_media(source, options)
    account = json_body(session.http.get("/v1/account"), session.credentials)
    check_account(account, media)
    key = options.new_key()
    state = ResumeState("", key, media.size, media.duration_seconds)
    body = create_body(media, options, key, title=options.title)
    tracker = Tracker(key, callers=callbacks.raised, credentials=session.credentials)

    def run() -> Transcript:
        callbacks.progress(UploadingProgress(0, 0, state.size))
        tracker.sent = True
        created = create(session, body)
        return _after_create(session, created, tracker, state, source, options, callbacks)

    return annotated(tracker, run)


def read_job_to_resume(session: SyncSession, job_id: str) -> Job:
    """The job a token names; a 404 means it was deleted or pruned (spec 7.3)."""
    try:
        return get_job(session, segment(job_id))
    except NotFoundError as missing:
        raise job_missing() from missing


def run_resume(
    session: SyncSession,
    token: str,
    file: FileInput | None,
    options: Options,
    callbacks: Callbacks,
) -> Transcript:
    options.validate()
    state = decode_token(token)
    source = early_source(state, file)
    tracker = Tracker(
        state.idempotency_key,
        token,
        sent=True,
        callers=callbacks.raised,
        credentials=session.credentials,
    )

    def run() -> Transcript:
        job = read_job_to_resume(session, state.job_id)
        if job.state != UPLOADING:
            return fetch_transcript(
                session,
                wait_job(
                    session, segment(state.job_id), options.wait_timeout, callbacks, token, job
                ),
            )
        late = late_source(state, file, source)
        callbacks.progress(UploadingProgress(0, 0, state.size))
        created = create(session, replay_body(state))
        if created.job_id != state.job_id:
            raise job_missing()
        return _after_create(session, created, tracker, state, late, options, callbacks)

    return annotated(tracker, run)
