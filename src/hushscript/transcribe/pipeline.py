from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from hushscript._errors import HushscriptError, NotFoundError, raise_for_response
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
from .source import FileInput, Source, make_source
from .upload import SyncUploader, parse_created, stream_size_mismatch
from .wait import finish, job_from, transcript_of, wait_for_job

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping

    from hushscript._models import Progress
    from hushscript.transcript import Transcript

    from .session import SyncSession
    from .upload import Created

UPLOADING: Final = "uploading"
RESUME_NOTE: Final = "The job exists on the server. Resume it with this token: "
SENT_NOTE: Final = "The create request was sent, so the job may exist. Idempotency key: "


@dataclass(slots=True)
class Tracker:
    """What an error raised after the create was sent has to carry (spec 7.3)."""

    key: str
    token: str | None = None
    sent: bool = False
    """True from the moment the create goes out: the server may have committed it."""

    def note(self) -> str:
        if self.token is None:
            return f"{SENT_NOTE}{self.key}"
        return f"{RESUME_NOTE}{self.token} (idempotency key {self.key})"


@contextmanager
def annotated(tracker: Tracker) -> Generator[None]:
    try:
        yield
    except (asyncio.CancelledError, KeyboardInterrupt) as interrupted:
        # Spec 7.4 and R26: an interrupt is never converted (asyncio.timeout and task groups
        # depend on it); once the create is out, the way back to the job rides along as a note.
        if tracker.sent:
            interrupted.add_note(tracker.note())
        raise
    except HushscriptError as error:
        error.idempotency_key = tracker.key
        if tracker.token is not None and error.resume_token is None:
            error.resume_token = tracker.token
        raise


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

    def progress(self, event: Progress) -> None:
        if self.on_progress is not None:
            self.on_progress(event)


def percent(sent: int, total: int) -> int:
    return min(100, sent * 100 // total) if total else 100


def create(session: SyncSession, body: Mapping[str, object]) -> Created:
    """`POST /v1/uploads`; the transport paces it to the 4 per minute the API allows (spec 7.5)."""
    response = session.http.post("/v1/uploads", json=body)
    return parsed(response, session.credentials, parse_created)


def get_job(session: SyncSession, job_id: str) -> Job:
    return job_from(session.http.get(f"/v1/jobs/{job_id}"), session.credentials)


def wait_job(
    session: SyncSession,
    job_id: str,
    wait_timeout: float,
    callbacks: Callbacks,
    token: str | None,
    first: Job | None = None,
) -> Job:
    return wait_for_job(
        lambda: get_job(session, job_id),
        session.clock,
        wait_timeout,
        callbacks.on_progress,
        token,
        first,
    )


def fetch_transcript(session: SyncSession, job: Job) -> Transcript:
    transcript_id = finish(job)
    return transcript_of(session.http.get(f"/v1/transcripts/{transcript_id}"), session.credentials)


def _upload(
    session: SyncSession,
    created: Created,
    source: Source,
    concurrency: int,
    callbacks: Callbacks,
) -> None:
    job_path = f"/v1/uploads/{created.job_id}"
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
    if callbacks.on_resume_token is not None:
        callbacks.on_resume_token(token)
    if created.state == UPLOADING:
        if source is None:
            raise file_required()
        _upload(session, created, source, options.concurrency, callbacks)
    job = wait_job(session, created.job_id, options.wait_timeout, callbacks, token)
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
    check_account(account, media, options)
    key = options.new_key()
    state = ResumeState("", key, media.size, media.duration_seconds)
    body = create_body(media, options, key, title=options.title)
    tracker = Tracker(key)
    with annotated(tracker):
        callbacks.progress(UploadingProgress(0, 0, state.size))
        tracker.sent = True
        created = create(session, body)
        return _after_create(session, created, tracker, state, source, options, callbacks)


def read_job_to_resume(session: SyncSession, job_id: str) -> Job:
    """The job a token names; a 404 means it was deleted or pruned (spec 7.3)."""
    try:
        return get_job(session, job_id)
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
    tracker = Tracker(state.idempotency_key, token, sent=True)
    with annotated(tracker):
        job = read_job_to_resume(session, state.job_id)
        if job.state != UPLOADING:
            return fetch_transcript(
                session,
                wait_job(session, state.job_id, options.wait_timeout, callbacks, token, job),
            )
        source = late_source(state, file, source)
        callbacks.progress(UploadingProgress(0, 0, state.size))
        created = create(session, replay_body(state))
        if created.job_id != state.job_id:
            raise job_missing()
        return _after_create(session, created, tracker, state, source, options, callbacks)
