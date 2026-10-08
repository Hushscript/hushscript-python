from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from hushscript._errors import NetworkError, raise_for_response
from hushscript._http import STREAM_EXTENSION, release
from hushscript._log import hiding_signed_url
from hushscript._response import parsed

from .segment import segment
from .upload import (
    OCTET_STREAM,
    PART_TIMEOUTS,
    Action,
    PartAttempts,
    Plan,
    UploadState,
    UrlBook,
    etag_missing,
    etag_of,
    exhausted,
    first_mode,
    parse_plan,
    part_url_missing,
    plan_for,
    r2_extensions,
    read_part,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from hushscript._redact import Secret

    from .session import AsyncSession
    from .source import Source


class AsyncUploader:
    """The asyncio twin of `SyncUploader`: `concurrency` worker tasks in a task group, so one
    failed part cancels the others."""

    def __init__(
        self,
        session: AsyncSession,
        job_id: str,
        plan: Plan | None,
        source: Source,
        concurrency: int,
    ) -> None:
        self._session = session
        self._job_id = job_id
        self._source = source
        self.plan = plan_for(plan, source.size)
        self.state = UploadState(first_mode(plan))
        self._book = UrlBook(session.clock)
        self._book.store(self.plan.urls, self.plan.next_part)
        self._pages = asyncio.Lock()
        self._width = 1 if source.sequential else concurrency
        self._sent = 0

    async def upload(self, on_bytes: Callable[[int], None]) -> None:
        numbers = iter(range(1, self.plan.total_parts + 1))

        async def worker() -> None:
            for n in numbers:
                size = await self._upload_part(n)
                self._sent += size
                on_bytes(self._sent)

        try:
            async with asyncio.TaskGroup() as group:
                for _ in range(self._width):
                    group.create_task(worker())
        except ExceptionGroup as failed:
            raise failed.exceptions[0] from None

    async def _read(self, n: int) -> bytes:
        return await asyncio.to_thread(read_part, self._source, self.plan, n)

    async def _upload_part(self, n: int) -> int:
        data = await self._read(n)
        attempts = PartAttempts()
        while True:
            if self.state.proxied:
                await self._put_proxied(n, data)
                return len(data)
            url = await self._url_for(n)
            if url is None:
                continue
            status, etag = await self._put_direct(n, url, data)
            if etag is not None:
                if not self.state.record(n, etag):
                    await self._put_proxied(n, data)
                return len(data)
            action = self.state.decide(attempts, status)
            if action is Action.EXHAUSTED:
                raise exhausted(n)
            if action is Action.REFRESH:
                await self._refresh(n, url)

    async def _put_direct(self, n: int, url: Secret, data: bytes) -> tuple[int | None, str | None]:
        client = self._session.r2
        try:
            with hiding_signed_url(f"r2:part/{n}"):
                response = await client.send(
                    client.build_request(
                        "PUT",
                        url.reveal(),
                        content=data,
                        timeout=PART_TIMEOUTS,
                        extensions=r2_extensions(n),
                    ),
                    stream=True,
                )
            try:
                etag = etag_of(response)
                if response.is_success and etag is None:
                    raise etag_missing(n)
                return response.status_code, etag
            finally:
                try:
                    await response.aclose()
                finally:
                    release(response.request)
        except NetworkError:
            return None, None

    async def _put_proxied(self, n: int, data: bytes) -> None:
        client = self._session.http
        response = await client.send(
            client.build_request(
                "PUT",
                f"/v1/uploads/{segment(self._job_id)}/parts/{n}",
                content=data,
                headers=OCTET_STREAM,
                timeout=PART_TIMEOUTS,
                extensions={STREAM_EXTENSION: True},
            ),
            stream=True,
        )
        try:
            if not response.is_success:
                await response.aread()
                raise_for_response(response, credentials=self._session.credentials)
        finally:
            try:
                await response.aclose()
            finally:
                release(response.request)

    async def _url_for(self, n: int) -> Secret | None:
        async with self._pages:
            url = self._book.get(n)
            if url is None:
                await self._fetch_for(n)
                if self.state.proxied:
                    return None
                url = self._book.get(n)
            if url is None:
                raise part_url_missing(n)
            return url

    async def _fetch_for(self, n: int) -> None:
        start = self._book.next_start
        if start is None or n < start:
            await self._fetch(n, advance=False)
            return
        while (
            self._book.get(n) is None
            and self._book.next_start is not None
            and not self.state.proxied
        ):
            await self._fetch(self._book.next_start, advance=True)

    async def _refresh(self, n: int, failed_url: Secret) -> None:
        async with self._pages:
            if self._book.is_current(n, failed_url):
                await self._fetch(n, advance=False)

    async def _fetch(self, start: int, *, advance: bool) -> None:
        response = await self._session.http.get(
            f"/v1/uploads/{segment(self._job_id)}/part-urls", params={"start": start}
        )
        plan = parsed(response, self._session.credentials, parse_plan)
        if not plan.direct and self.state.fall_back():
            return
        cursor = plan.next_part if advance else self._book.next_start
        if advance and cursor is not None and cursor <= start:
            cursor = None
        self._book.store(plan.urls, cursor)
