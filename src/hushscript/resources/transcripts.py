from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hushscript._json import as_dict, as_list
from hushscript._response import parsed
from hushscript._shape import (
    as_text,
    as_whole,
    check_shape,
    maybe_text,
    to_datetime,
)
from hushscript._shapes import DELETED_LIST, TRANSCRIPT_LIST
from hushscript.paginate import Page, apaginate, paginate
from hushscript.resources._params import check_page_size, list_params, path_id
from hushscript.transcript import Transcript

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from datetime import datetime

    from hushscript.transcribe.session import AsyncSession, SyncSession


@dataclass(frozen=True, slots=True)
class TranscriptSummary:
    """One row of the transcript list."""

    id: str
    title: str
    language: str | None
    duration_seconds: int
    created_at: datetime
    auto_delete_at: datetime | None
    tags: list[str]

    __hash__ = None  # type: ignore[assignment]  # holds a list, so it is unhashable by design


@dataclass(frozen=True, slots=True)
class DeletedTranscript:
    """The record kept after a transcript was removed; its content is gone."""

    id: str
    title: str
    duration_seconds: int
    created_at: datetime
    """When the transcript was uploaded."""
    deleted_at: datetime
    cause: str
    """`manual`, `scheduled`, `dormant` or `expired`; a cause the SDK does not know yet passes
    through as the API's own string."""
    receipt: dict[str, object] | None
    """The stored deletion receipt, opaque and as the API sends it (snake_case keys, string
    timestamps); None when it could not be read back."""

    __hash__ = None  # type: ignore[assignment]  # holds a dict, so it is unhashable by design


def summary_page(body: object) -> Page[TranscriptSummary]:
    check_shape(body, TRANSCRIPT_LIST, "transcript list response")
    fields = as_dict(body) or {}
    items: list[TranscriptSummary] = []
    for row in as_list(fields["transcripts"]) or []:
        item = as_dict(row) or {}
        auto_delete = item["auto_delete_at"]
        items.append(
            TranscriptSummary(
                id=as_text(item["id"]),
                title=as_text(item["title"]),
                language=maybe_text(item["language_detected"]),
                duration_seconds=as_whole(item["duration_seconds"]),
                created_at=to_datetime(item["created_at"]),
                auto_delete_at=None if auto_delete is None else to_datetime(auto_delete),
                tags=[as_text(tag) for tag in as_list(item["tags"]) or []],
            )
        )
    return Page(items=items, next_cursor=maybe_text(fields["next_cursor"]))


def deleted_page(body: object) -> Page[DeletedTranscript]:
    check_shape(body, DELETED_LIST, "deleted transcript list response")
    fields = as_dict(body) or {}
    items: list[DeletedTranscript] = []
    for row in as_list(fields["deleted"]) or []:
        item = as_dict(row) or {}
        items.append(
            DeletedTranscript(
                id=as_text(item["id"]),
                title=as_text(item["title"]),
                duration_seconds=as_whole(item["duration_seconds"]),
                created_at=to_datetime(item["created_at"]),
                deleted_at=to_datetime(item["deleted_at"]),
                cause=as_text(item["cause"]),
                receipt=as_dict(item["receipt"]),
            )
        )
    return Page(items=items, next_cursor=maybe_text(fields["next_cursor"]))


class Transcripts:
    """`hs.transcripts`: the account's finished transcripts. Ones still processing are jobs: see
    `hs.jobs.list(active=True)`."""

    def __init__(self, session: SyncSession) -> None:
        self._session = session

    def list(self, *, page_size: int | None = None) -> Iterator[TranscriptSummary]:
        """Every finished transcript, newest first, fetching pages as it goes. `page_size` is 1 to
        100 (the API clamps it there) and defaults to 50."""
        check_page_size(page_size)
        return paginate(lambda cursor: self._page(cursor, page_size))

    def page(
        self, *, cursor: str | None = None, page_size: int | None = None
    ) -> Page[TranscriptSummary]:
        """One page of `list()`; `cursor` is a previous page's `next_cursor`."""
        check_page_size(page_size)
        return self._page(cursor, page_size)

    def get(self, transcript_id: str) -> Transcript:
        path = f"/v1/transcripts/{path_id(transcript_id)}"
        return parsed(self._session.http.get(path), self._session.credentials, Transcript.from_api)

    def deleted(self) -> Iterator[DeletedTranscript]:
        """The deletion records, by upload time, newest first."""
        return paginate(self._deleted_page)

    def _page(self, cursor: str | None, page_size: int | None) -> Page[TranscriptSummary]:
        response = self._session.http.get("/v1/transcripts", params=list_params(cursor, page_size))
        return parsed(response, self._session.credentials, summary_page)

    def _deleted_page(self, cursor: str | None) -> Page[DeletedTranscript]:
        response = self._session.http.get(
            "/v1/transcripts/deleted", params=list_params(cursor, None)
        )
        return parsed(response, self._session.credentials, deleted_page)


class AsyncTranscripts:
    """`hs.transcripts` on the asyncio client; the lists are async iterators."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def list(self, *, page_size: int | None = None) -> AsyncIterator[TranscriptSummary]:
        check_page_size(page_size)
        return apaginate(lambda cursor: self._page(cursor, page_size))

    async def page(
        self, *, cursor: str | None = None, page_size: int | None = None
    ) -> Page[TranscriptSummary]:
        check_page_size(page_size)
        return await self._page(cursor, page_size)

    async def get(self, transcript_id: str) -> Transcript:
        path = f"/v1/transcripts/{path_id(transcript_id)}"
        response = await self._session.http.get(path)
        return parsed(response, self._session.credentials, Transcript.from_api)

    def deleted(self) -> AsyncIterator[DeletedTranscript]:
        return apaginate(self._deleted_page)

    async def _page(self, cursor: str | None, page_size: int | None) -> Page[TranscriptSummary]:
        response = await self._session.http.get(
            "/v1/transcripts", params=list_params(cursor, page_size)
        )
        return parsed(response, self._session.credentials, summary_page)

    async def _deleted_page(self, cursor: str | None) -> Page[DeletedTranscript]:
        response = await self._session.http.get(
            "/v1/transcripts/deleted", params=list_params(cursor, None)
        )
        return parsed(response, self._session.credentials, deleted_page)
