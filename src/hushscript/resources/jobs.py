from __future__ import annotations

from typing import TYPE_CHECKING

from hushscript._json import as_dict, as_list, extra_fields
from hushscript._models import Job
from hushscript._response import parsed
from hushscript._shape import check_shape, maybe_text
from hushscript._shapes import JOB_LIST
from hushscript.paginate import Page, apaginate, paginate
from hushscript.resources._params import path_id
from hushscript.transcribe import apipeline, pipeline
from hushscript.transcribe.pipeline import Callbacks
from hushscript.transcribe.preflight import check_wait_timeout
from hushscript.transcribe.wait import DEFAULT_WAIT_TIMEOUT

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from hushscript._models import Progress
    from hushscript.transcribe.session import AsyncSession, SyncSession


def job_page(body: object) -> Page[Job]:
    check_shape(body, JOB_LIST, "job list response")
    fields = as_dict(body) or {}
    items = [Job.from_body(row) for row in as_list(fields["jobs"]) or []]
    return Page(
        _extra=extra_fields(fields, "jobs", "next_cursor"),
        items=items,
        next_cursor=maybe_text(fields["next_cursor"]),
    )


def job_params(cursor: str | None, *, active: bool) -> dict[str, str]:
    params: dict[str, str] = {}
    if active:
        params["active"] = "true"
    if cursor is not None:
        params["cursor"] = cursor
    return params


class Jobs:
    """`hs.jobs`: the account's transcription jobs."""

    def __init__(self, session: SyncSession) -> None:
        self._session = session

    def list(self, *, active: bool = False) -> Iterator[Job]:
        """Every job, newest first, fetching pages as it goes; `active=True` keeps only the jobs
        that have not finished."""
        return paginate(lambda cursor: self._page(cursor, active=active))

    def get(self, job_id: str) -> Job:
        return pipeline.get_job(self._session, path_id(job_id))

    def wait(
        self,
        job_id: str,
        *,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
        on_progress: Callable[[Progress], None] | None = None,
    ) -> Job:
        """Polls until the job is `done` or `failed` (spec 8.6); WaitTimeoutError after
        `wait_timeout` seconds. A failed job is returned, not raised."""
        check_wait_timeout(wait_timeout)
        return pipeline.wait_job(
            self._session, path_id(job_id), wait_timeout, Callbacks(on_progress=on_progress), None
        )

    def _page(self, cursor: str | None, *, active: bool) -> Page[Job]:
        response = self._session.http.get("/v1/jobs", params=job_params(cursor, active=active))
        return parsed(response, self._session.credentials, job_page)


class AsyncJobs:
    """`hs.jobs` on the asyncio client; `list` is an async iterator."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def list(self, *, active: bool = False) -> AsyncIterator[Job]:
        return apaginate(lambda cursor: self._page(cursor, active=active))

    async def get(self, job_id: str) -> Job:
        return await apipeline.get_job(self._session, path_id(job_id))

    async def wait(
        self,
        job_id: str,
        *,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
        on_progress: Callable[[Progress], None] | None = None,
    ) -> Job:
        check_wait_timeout(wait_timeout)
        return await apipeline.wait_job(
            self._session, path_id(job_id), wait_timeout, Callbacks(on_progress=on_progress), None
        )

    async def _page(self, cursor: str | None, *, active: bool) -> Page[Job]:
        response = await self._session.http.get(
            "/v1/jobs", params=job_params(cursor, active=active)
        )
        return parsed(response, self._session.credentials, job_page)
