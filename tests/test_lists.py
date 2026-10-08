from __future__ import annotations

import asyncio
from dataclasses import fields
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

from helpers import error_body, job_body, reply, transcript_body
from hushscript import (
    OPERATION_SCOPES,
    ApiError,
    DeletedTranscript,
    HushscriptError,
    Job,
    NotFoundError,
    Page,
    PermissionDeniedError,
    PreflightError,
    TranscriptSummary,
)
from routes import async_hs_on, hs_on

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Generator, Iterator


def row(number: int) -> dict[str, object]:
    return {
        "id": f"tr_{number:03d}",
        "title": f"Call {number}",
        "language_detected": None,
        "duration_seconds": 60,
        "created_at": 1_700_000_000 - number,
        "auto_delete_at": None,
        "tags": ["t"],
        "options": {},
        "insights_state": "none",
    }


def pager(total: int, size: int = 2) -> Callable[[httpx.Request], httpx.Response]:
    """`GET /v1/transcripts` over `total` rows, `size` to a page, cursors `c<offset>`."""

    def handle(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        start = 0 if cursor is None else int(cursor.removeprefix("c"))
        stop = min(start + size, total)
        rows = [row(n) for n in range(start + 1, stop + 1)]
        return reply(
            200, {"transcripts": rows, "next_cursor": f"c{stop}" if stop < total else None}
        )

    return handle


def test_list_walks_every_page_and_sends_a_cursor_only_after_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = hs_on(monkeypatch, pager(5))
    rows = list(hs.transcripts.list())
    assert [r.id for r in rows] == [f"tr_{n:03d}" for n in range(1, 6)]
    assert routes.queries() == [{}, {"cursor": "c2"}, {"cursor": "c4"}]
    first = rows[0]
    assert isinstance(first, TranscriptSummary)
    assert first.created_at == datetime(2023, 11, 14, 22, 13, 19, tzinfo=UTC)
    assert (first.title, first.language, first.duration_seconds, first.tags) == (
        "Call 1",
        None,
        60,
        ["t"],
    )
    assert first.auto_delete_at is None


def test_list_is_lazy_and_closing_it_sends_no_further_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = hs_on(monkeypatch, pager(6))
    items = hs.transcripts.list()
    assert routes.requests == []
    assert next(items).id == "tr_001"
    assert next(items).id == "tr_002"
    assert len(routes.requests) == 1
    cast("Generator[TranscriptSummary]", items).close()
    assert len(routes.requests) == 1
    assert next(items, None) is None


def test_a_page_size_goes_out_as_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = hs_on(monkeypatch, pager(3, size=3))
    assert len(list(hs.transcripts.list(page_size=3))) == 3
    assert routes.queries() == [{"limit": "3"}]
    assert len(routes.requests) == 1


@pytest.mark.parametrize("bad_size", [0, -1, True, 1.5, "5"])
def test_page_size_is_invalid_before_any_request(
    monkeypatch: pytest.MonkeyPatch, bad_size: object
) -> None:
    hs, routes = hs_on(monkeypatch, pager(1))
    for call in (hs.transcripts.list, hs.transcripts.page):
        with pytest.raises(PreflightError) as raised:
            call(page_size=bad_size)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert routes.requests == []


def test_page_reads_one_page_and_hands_back_the_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    hs, routes = hs_on(monkeypatch, pager(5))
    first = hs.transcripts.page(page_size=2)
    assert isinstance(first, Page)
    assert [r.id for r in first.items] == ["tr_001", "tr_002"]
    assert first.next_cursor == "c2"
    second = hs.transcripts.page(cursor=first.next_cursor, page_size=2)
    assert [r.id for r in second.items] == ["tr_003", "tr_004"]
    assert routes.queries() == [{"limit": "2"}, {"limit": "2", "cursor": "c2"}]
    assert hs.transcripts.page(cursor="c4").next_cursor is None


def test_an_empty_list_ends_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    hs, routes = hs_on(monkeypatch, pager(0))
    assert list(hs.transcripts.list()) == []
    assert len(routes.requests) == 1


def stuck(request: httpx.Request) -> httpx.Response:
    cursor = request.url.params.get("cursor")
    sent = 0 if cursor is None else int(cursor)
    return reply(200, {"transcripts": [row(sent + 1)], "next_cursor": "7"})


def test_a_cursor_equal_to_the_one_just_sent_is_a_pagination_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = hs_on(monkeypatch, stuck)
    seen: list[str] = []
    with pytest.raises(HushscriptError) as raised:
        seen.extend(item.id for item in hs.transcripts.list())
    assert (raised.value.code, raised.value.status) == ("pagination_loop", None)
    assert type(raised.value) is HushscriptError
    # The page that repeats the cursor it was sent still yields its items before the error.
    assert routes.queries() == [{}, {"cursor": "7"}]
    assert seen == ["tr_001", "tr_008"]


def test_the_deleted_records_page_and_keep_the_receipt_as_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = {"deleted_at": "2026-01-01T00:00:00Z", "items": [{"kind": "audio"}]}

    def handle(request: httpx.Request) -> httpx.Response:
        first = "cursor" not in request.url.params
        record = {
            "id": "tr_a" if first else "tr_b",
            "title": "Gone",
            "duration_seconds": 30,
            "created_at": 1_700_000_000,
            "deleted_at": 1_700_000_500,
            "cause": "manual" if first else "future_cause",
            "receipt": receipt if first else None,
        }
        return reply(200, {"deleted": [record], "next_cursor": "c1" if first else None})

    hs, routes = hs_on(monkeypatch, handle)
    records = list(hs.transcripts.deleted())
    assert [(r.id, r.cause) for r in records] == [("tr_a", "manual"), ("tr_b", "future_cause")]
    assert records[0].receipt == receipt
    assert records[1].receipt is None
    assert records[0].deleted_at == datetime(2023, 11, 14, 22, 21, 40, tzinfo=UTC)
    assert routes.requests[0].url.path == "/v1/transcripts/deleted"
    assert routes.queries() == [{}, {"cursor": "c1"}]


def jobs_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/jobs":
        later = request.url.params.get("cursor") == "j2"
        jobs = [job_body("job_2", "mystery_state")] if later else [job_body("job_1", "done")]
        return reply(200, {"jobs": jobs, "next_cursor": None if later else "j2"})
    return reply(200, job_body(request.url.path.rsplit("/", 1)[1], "queued"))


def test_jobs_list_passes_active_and_walks_the_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    hs, routes = hs_on(monkeypatch, jobs_handler)
    jobs = list(hs.jobs.list(active=True))
    assert [(j.id, j.state) for j in jobs] == [("job_1", "done"), ("job_2", "mystery_state")]
    assert routes.queries() == [{"active": "true"}, {"active": "true", "cursor": "j2"}]
    list(hs.jobs.list(active=False))
    assert routes.queries()[2:] == [{}, {"cursor": "j2"}]


def test_a_job_maps_the_spec_fields_and_leaves_the_private_ones_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = job_body(
        "job_9",
        "failed",
        error="media unreadable",
        failure_kind="media_unreadable",
        declared_seconds=60,
        verified_seconds=59,
        actual_seconds=58,
        billable_seconds=60,
        retry_of="job_8",
        transcript_id=None,
        private_result_available=True,
    )
    hs, _ = hs_on(monkeypatch, lambda _request: reply(200, body))
    job = hs.jobs.get("job_9")
    assert isinstance(job, Job)
    assert (job.id, job.state, job.mode, job.error, job.failure_kind) == (
        "job_9",
        "failed",
        "standard",
        "media unreadable",
        "media_unreadable",
    )
    assert (job.declared_seconds, job.verified_seconds, job.actual_seconds) == (60, 59, 58)
    assert (job.billable_seconds, job.retry_of, job.transcript_id) == (60, "job_8", None)
    assert job.created_at == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert job.options.speaker_detection is True
    assert job.options.language_code is None
    assert job.options.translation_targets == []
    assert job.options.auto_generate_insights is None
    names = {field.name for field in fields(Job)}
    assert not {name for name in names if "private" in name or "fetch" in name}
    assert "raw" not in names


def test_a_job_the_api_does_not_know_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = httpx.Response(404, json=error_body("not_found", 1000))
    hs, _ = hs_on(monkeypatch, lambda _request: missing)
    with pytest.raises(NotFoundError):
        hs.jobs.get("job_none")


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("transcripts", {"transcripts": [{"id": "tr_1"}], "next_cursor": None}),
        ("transcripts", {"transcripts": [], "next_cursor": 5}),
        ("transcripts", {"transcripts": {}, "next_cursor": None}),
        ("transcripts", [row(1)]),
        ("deleted", {"deleted": [{**row(1), "deleted_at": "x"}], "next_cursor": None}),
        ("jobs", {"jobs": [{"id": "j"}], "next_cursor": None}),
        ("jobs", {"jobs": [job_body("j", "done", created_at=None)], "next_cursor": None}),
    ],
)
def test_a_list_body_that_does_not_fit_is_a_bad_response(
    monkeypatch: pytest.MonkeyPatch, path: str, body: object
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _request: reply(200, body))
    sources: dict[str, Callable[[], Iterator[object]]] = {
        "transcripts": hs.transcripts.list,
        "deleted": hs.transcripts.deleted,
        "jobs": hs.jobs.list,
    }
    with pytest.raises(ApiError) as raised:
        list(sources[path]())
    assert (raised.value.code, raised.value.status, raised.value.numeric_code) == (
        "bad_response",
        200,
        None,
    )


def test_a_list_error_is_the_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    denied = httpx.Response(403, json=error_body("pat_scope_missing", 2023))
    hs, _ = hs_on(monkeypatch, lambda _request: denied)
    with pytest.raises(PermissionDeniedError) as raised:
        list(hs.transcripts.list())
    assert (raised.value.code, raised.value.status) == ("pat_scope_missing", 403)
    assert OPERATION_SCOPES["GET /v1/transcripts"] in (raised.value.hint or "")


@pytest.mark.anyio
async def test_the_async_list_walks_pages_and_checks_the_page_size_up_front(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = async_hs_on(monkeypatch, pager(5))
    rows = [item.id async for item in hs.transcripts.list()]
    assert rows == [f"tr_{n:03d}" for n in range(1, 6)]
    assert routes.queries() == [{}, {"cursor": "c2"}, {"cursor": "c4"}]
    with pytest.raises(PreflightError):
        hs.transcripts.list(page_size=0)
    page = await hs.transcripts.page(cursor="c2", page_size=2)
    assert page.next_cursor == "c4"


@pytest.mark.anyio
async def test_the_async_list_detects_a_loop_and_serves_jobs_and_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = async_hs_on(monkeypatch, stuck)
    with pytest.raises(HushscriptError) as raised:
        _ = [item async for item in hs.transcripts.list()]
    assert (raised.value.code, raised.value.status) == ("pagination_loop", None)
    hs, _ = async_hs_on(monkeypatch, jobs_handler)
    assert [job.id async for job in hs.jobs.list(active=True)] == ["job_1", "job_2"]
    assert (await hs.jobs.get("job_3")).state == "queued"
    hs, _ = async_hs_on(
        monkeypatch, lambda _request: reply(200, {"deleted": [], "next_cursor": None})
    )
    assert [r async for r in hs.transcripts.deleted()] == []


@pytest.mark.anyio
async def test_cancelling_the_async_list_between_pages_stops_the_walk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = asyncio.Event()
    hs, routes = async_hs_on(monkeypatch, pager(10))
    seen: list[str] = []

    async def drain() -> None:
        async for item in hs.transcripts.list():
            seen.append(item.id)
            if len(seen) == 2:
                gate.set()
                await asyncio.sleep(3600)  # parked between pages until the cancel

    task = asyncio.create_task(drain())
    await gate.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert seen == ["tr_001", "tr_002"]
    assert len(routes.requests) == 1


@pytest.mark.anyio
async def test_a_bad_async_page_is_a_bad_response(monkeypatch: pytest.MonkeyPatch) -> None:
    hs, _ = async_hs_on(monkeypatch, lambda _request: reply(200, {"transcripts": 1}))
    with pytest.raises(ApiError) as raised:
        _ = [item async for item in hs.transcripts.list()]
    assert raised.value.code == "bad_response"
    hs, _ = async_hs_on(monkeypatch, lambda _request: reply(200, transcript_body()))
    with pytest.raises(ApiError):
        _ = [item async for item in hs.jobs.list()]


def test_a_summary_and_a_deleted_record_are_unhashable_by_design(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, pager(1))
    summary = next(hs.transcripts.list())
    for value in (
        summary,
        DeletedTranscript(
            id="a",
            title="t",
            duration_seconds=1,
            created_at=summary.created_at,
            deleted_at=summary.created_at,
            cause="manual",
            receipt=None,
        ),
    ):
        with pytest.raises(TypeError, match="unhashable"):
            hash(value)


@pytest.mark.parametrize("bad_size", [0, -1, True, 1.5, "5"])
@pytest.mark.anyio
async def test_async_page_size_is_invalid_before_any_request(
    monkeypatch: pytest.MonkeyPatch, bad_size: object
) -> None:
    hs, routes = async_hs_on(monkeypatch, pager(1))
    with pytest.raises(PreflightError) as raised:
        hs.transcripts.list(page_size=bad_size)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    with pytest.raises(PreflightError) as raised:
        await hs.transcripts.page(page_size=bad_size)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
    assert (raised.value.code, raised.value.status) == ("invalid_option", None)
    assert routes.requests == []


@pytest.mark.anyio
async def test_async_jobs_active_false_omits_the_filter_on_every_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = async_hs_on(monkeypatch, jobs_handler)
    assert [job.id async for job in hs.jobs.list(active=False)] == ["job_1", "job_2"]
    assert routes.queries() == [{}, {"cursor": "j2"}]


@pytest.mark.parametrize("page_size", [1, 100, 101])
def test_page_size_is_sent_without_a_client_side_upper_clamp(
    monkeypatch: pytest.MonkeyPatch, page_size: int
) -> None:
    hs, routes = hs_on(monkeypatch, pager(1))
    assert hs.transcripts.page(page_size=page_size).items[0].id == "tr_001"
    assert next(hs.transcripts.list(page_size=page_size)).id == "tr_001"
    assert routes.queries() == [{"limit": str(page_size)}, {"limit": str(page_size)}]


@pytest.mark.parametrize("page_size", [1, 100, 101])
@pytest.mark.anyio
async def test_async_page_size_is_sent_without_a_client_side_upper_clamp(
    monkeypatch: pytest.MonkeyPatch, page_size: int
) -> None:
    hs, routes = async_hs_on(monkeypatch, pager(1))
    assert (await hs.transcripts.page(page_size=page_size)).items[0].id == "tr_001"
    assert [item.id async for item in hs.transcripts.list(page_size=page_size)] == ["tr_001"]
    assert routes.queries() == [{"limit": str(page_size)}, {"limit": str(page_size)}]


@pytest.mark.parametrize("cursor", ["7", " ", "\t", "\u2003"])
def test_single_page_rejects_the_cursor_just_sent(
    monkeypatch: pytest.MonkeyPatch, cursor: str
) -> None:
    hs, routes = hs_on(
        monkeypatch, lambda _request: reply(200, {"transcripts": [row(1)], "next_cursor": cursor})
    )
    with pytest.raises(HushscriptError) as raised:
        hs.transcripts.page(cursor=cursor)
    assert type(raised.value) is HushscriptError
    assert (raised.value.code, raised.value.status) == ("pagination_loop", None)
    assert str(raised.value) == (
        "The API returned the same page cursor it was sent; stopping instead of repeating it."
    )
    assert routes.queries() == [{"cursor": cursor}]


@pytest.mark.parametrize("cursor", ["7", " ", "\t", "\u2003"])
@pytest.mark.anyio
async def test_async_single_page_rejects_the_cursor_just_sent(
    monkeypatch: pytest.MonkeyPatch, cursor: str
) -> None:
    hs, routes = async_hs_on(
        monkeypatch, lambda _request: reply(200, {"transcripts": [row(1)], "next_cursor": cursor})
    )
    with pytest.raises(HushscriptError) as raised:
        await hs.transcripts.page(cursor=cursor)
    assert type(raised.value) is HushscriptError
    assert (raised.value.code, raised.value.status) == ("pagination_loop", None)
    assert str(raised.value) == (
        "The API returned the same page cursor it was sent; stopping instead of repeating it."
    )
    assert routes.queries() == [{"cursor": cursor}]


@pytest.mark.parametrize(
    ("cursor", "next_cursor"),
    [(None, None), (None, ""), ("", ""), ("7", None), ("7", ""), ("7", "8")],
)
def test_single_page_accepts_terminal_and_advancing_cursors(
    monkeypatch: pytest.MonkeyPatch, cursor: str | None, next_cursor: str | None
) -> None:
    hs, _ = hs_on(
        monkeypatch,
        lambda _request: reply(200, {"transcripts": [row(1)], "next_cursor": next_cursor}),
    )
    page = hs.transcripts.page(cursor=cursor)
    assert [item.id for item in page.items] == ["tr_001"]
    assert page.next_cursor == next_cursor


@pytest.mark.parametrize(
    ("cursor", "next_cursor"),
    [(None, None), (None, ""), ("", ""), ("7", None), ("7", ""), ("7", "8")],
)
@pytest.mark.anyio
async def test_async_single_page_accepts_terminal_and_advancing_cursors(
    monkeypatch: pytest.MonkeyPatch, cursor: str | None, next_cursor: str | None
) -> None:
    hs, _ = async_hs_on(
        monkeypatch,
        lambda _request: reply(200, {"transcripts": [row(1)], "next_cursor": next_cursor}),
    )
    page = await hs.transcripts.page(cursor=cursor)
    assert [item.id for item in page.items] == ["tr_001"]
    assert page.next_cursor == next_cursor


def deleted_row(number: int) -> dict[str, object]:
    return {
        "id": f"tr_d{number}",
        "title": "Gone",
        "duration_seconds": 30,
        "created_at": 1_700_000_000,
        "deleted_at": 1_700_000_500,
        "cause": "manual",
        "receipt": None,
    }


def stuck_on(kind: str) -> Callable[[httpx.Request], httpx.Response]:
    """Answers every page of a list with the same next_cursor, `7`."""

    def handle(request: httpx.Request) -> httpx.Response:
        number = 1 if request.url.params.get("cursor") is None else 2
        items = {
            "transcripts": {"transcripts": [row(number)]},
            "jobs": {"jobs": [job_body(f"job_{number}", "done")]},
            "deleted": {"deleted": [deleted_row(number)]},
        }[kind]
        return reply(200, {**items, "next_cursor": "7"})

    return handle


LOOPED = {
    "transcripts": ["tr_001", "tr_002"],
    "jobs": ["job_1", "job_2"],
    "deleted": ["tr_d1", "tr_d2"],
}


def listing(hs: Any, kind: str) -> Any:  # the sync and asyncio clients share the shape
    return {
        "transcripts": hs.transcripts.list,
        "jobs": hs.jobs.list,
        "deleted": hs.transcripts.deleted,
    }[kind]()


async def collect(items: AsyncIterator[Any], seen: list[str]) -> None:
    async for item in items:
        seen.append(item.id)  # noqa: PERF401  # the items before the error must stay


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("kind", ["transcripts", "jobs", "deleted"])
async def test_every_list_yields_the_page_that_repeats_its_cursor_then_raises_pagination_loop(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    asynchronous: bool,  # noqa: FBT001
) -> None:
    seen: list[str] = []
    if asynchronous:
        hs, routes = async_hs_on(monkeypatch, stuck_on(kind))
        with pytest.raises(HushscriptError) as raised:
            await collect(listing(hs, kind), seen)
    else:
        sync_hs, routes = hs_on(monkeypatch, stuck_on(kind))
        with pytest.raises(HushscriptError) as raised:
            seen.extend(item.id for item in listing(sync_hs, kind))
    assert type(raised.value) is HushscriptError
    assert (raised.value.code, raised.value.status) == ("pagination_loop", None)
    assert [query.get("cursor") for query in routes.queries()] == [None, "7"]
    assert seen == LOOPED[kind]
