from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar

from hushscript._errors import NotFoundError, raise_for_response
from hushscript._models import Job, UploadingProgress
from hushscript._response import json_body, parsed

from .aupload import AsyncUploader
from .heartbeat import Heartbeat
from .pipeline import UPLOADING, Callbacks, Tracker, annotated, percent, replay_body
from .preflight import Options, check_account, check_media, create_body
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
from .upload import parse_created, stream_size_mismatch
from .wait import await_job, finish, job_from, transcript_of

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from hushscript.transcript import Transcript

    from .session import AsyncSession
    from .upload import Created

T = TypeVar("T")


async def create(session: AsyncSession, body: Mapping[str, object]) -> Created:
    response = await session.http.post("/v1/uploads", json=body)
    return parsed(response, session.credentials, parse_created)


async def get_job(session: AsyncSession, job_id: str) -> Job:
    return job_from(await session.http.get(f"/v1/jobs/{job_id}"), session.credentials)


async def wait_job(
    session: AsyncSession,
    job_id: str,
    wait_timeout: float,
    callbacks: Callbacks,
    token: str | None,
    first: Job | None = None,
) -> Job:
    return await await_job(
        lambda: get_job(session, job_id),
        session.clock,
        wait_timeout,
        callbacks.progress,
        token,
        first,
    )


async def fetch_transcript(session: AsyncSession, job: Job) -> Transcript:
    transcript_id = finish(job)
    return transcript_of(
        await session.http.get(f"/v1/transcripts/{transcript_id}"), session.credentials
    )


async def _supervised(
    heartbeat: Heartbeat, ping: Callable[[], Awaitable[None]], work: Awaitable[T]
) -> T:
    """Runs `work` beside the heartbeat. A heartbeat that ends in `unauthorized` cancels the work
    and raises its error; one that ends in `wrong_state` just stops."""
    work_task = asyncio.ensure_future(work)
    beat_task = asyncio.ensure_future(heartbeat.arun(ping))
    try:
        waiting: set[asyncio.Future[Any]] = {work_task, beat_task}
        while True:
            done, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
            if work_task in done:
                return work_task.result()
            heartbeat.raise_if_failed()
            waiting = {work_task}
    finally:
        for task in (work_task, beat_task):
            task.cancel()
        await asyncio.gather(work_task, beat_task, return_exceptions=True)


async def _upload(
    session: AsyncSession,
    created: Created,
    source: Source,
    concurrency: int,
    callbacks: Callbacks,
) -> None:
    job_path = f"/v1/uploads/{created.job_id}"
    uploader = AsyncUploader(session, created.job_id, created.plan, source, concurrency)
    total = source.size

    async def ping() -> None:
        raise_for_response(
            await session.http.post(f"{job_path}/heartbeat"), credentials=session.credentials
        )

    async def parts_and_complete() -> None:
        await uploader.upload(
            lambda sent: callbacks.progress(UploadingProgress(percent(sent, total), sent, total))
        )
        if not await asyncio.to_thread(source.at_end):
            raise stream_size_mismatch()
        body = uploader.state.parts_body()
        response = (
            await session.http.post(f"{job_path}/complete")
            if body is None
            else await session.http.post(f"{job_path}/complete", json=body)
        )
        raise_for_response(response, credentials=session.credentials)

    await _supervised(Heartbeat(session.clock, session.log), ping, parts_and_complete())


async def _after_create(  # the upload, wait and fetch that follow a create
    session: AsyncSession,
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
        await _upload(session, created, source, options.concurrency, callbacks)
    job = await wait_job(session, created.job_id, options.wait_timeout, callbacks, token)
    return await fetch_transcript(session, job)


async def run_transcribe(
    session: AsyncSession,
    file: FileInput,
    options: Options,
    size: int | None,
    callbacks: Callbacks,
) -> Transcript:
    options.validate()
    source = make_source(file, size)
    media = await asyncio.to_thread(check_media, source, options)
    account = json_body(await session.http.get("/v1/account"), session.credentials)
    check_account(account, media, options)
    key = options.new_key()
    state = ResumeState("", key, media.size, media.duration_seconds)
    body = create_body(media, options, key, title=options.title)
    tracker = Tracker(key, callers=callbacks.raised)
    with annotated(tracker):
        callbacks.progress(UploadingProgress(0, 0, state.size))
        tracker.sent = True
        created = await create(session, body)
        return await _after_create(session, created, tracker, state, source, options, callbacks)


async def read_job_to_resume(session: AsyncSession, job_id: str) -> Job:
    try:
        return await get_job(session, job_id)
    except NotFoundError as missing:
        raise job_missing() from missing


async def run_resume(
    session: AsyncSession,
    token: str,
    file: FileInput | None,
    options: Options,
    callbacks: Callbacks,
) -> Transcript:
    options.validate()
    state = decode_token(token)
    source = early_source(state, file)
    tracker = Tracker(state.idempotency_key, token, sent=True, callers=callbacks.raised)
    with annotated(tracker):
        job = await read_job_to_resume(session, state.job_id)
        if job.state != UPLOADING:
            waited = await wait_job(
                session, state.job_id, options.wait_timeout, callbacks, token, job
            )
            return await fetch_transcript(session, waited)
        source = late_source(state, file, source)
        callbacks.progress(UploadingProgress(0, 0, state.size))
        created = await create(session, replay_body(state))
        if created.job_id != state.job_id:
            raise job_missing()
        return await _after_create(session, created, tracker, state, source, options, callbacks)
