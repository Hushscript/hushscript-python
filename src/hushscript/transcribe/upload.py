from __future__ import annotations

import enum
import math
import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import httpx

from hushscript._config import PART_TIMEOUT
from hushscript._errors import NetworkError, UploadError, raise_for_response
from hushscript._http import CLASS_EXTENSION, LABEL_EXTENSION, STREAM_EXTENSION, release
from hushscript._json import as_dict, as_list
from hushscript._log import hiding_signed_url
from hushscript._redact import Secret
from hushscript._response import BadBodyError, parsed
from hushscript._retry import RetryClass

from .segment import segment, usable_segment

if TYPE_CHECKING:
    from collections.abc import Callable

    from hushscript._clock import Clock

    from .heartbeat import Heartbeat
    from .session import SyncSession
    from .source import Source

MAX_PART_BYTES: Final = 32 * 1024 * 1024
URL_MAX_AGE: Final = 23 * 3600.0
PARTS_EXHAUSTED: Final = "parts_exhausted"
HTTP_FORBIDDEN: Final = 403
OCTET_STREAM: Final = {"Content-Type": "application/octet-stream"}


@dataclass(frozen=True, slots=True)
class Plan:
    """The direct-to-R2 plan of a create response (spec 8.3)."""

    part_size: int
    total_parts: int
    urls: dict[int, Secret]
    """Signed URLs, held where no repr, copy or pickle shows them."""
    next_part: int | None
    direct: bool = True
    """False when `part_urls` was `null`: direct upload is not available (R70) and every part goes
    through the API, whatever `next_part` says."""


@dataclass(frozen=True, slots=True)
class Created:
    job_id: str
    state: str
    plan: Plan | None
    """None in proxied mode (`upload: null`), which a job that has left `uploading` also shows;
    `state` tells them apart."""


def _whole(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _unexpected(what: str) -> BadBodyError:
    return BadBodyError(what)


def _urls(raw: object) -> dict[int, Secret]:
    urls: dict[int, Secret] = {}
    for item in as_list(raw) or []:
        entry = as_dict(item) or {}
        n = _whole(entry.get("n"))
        url = entry.get("url")
        if n is None or n < 1 or not isinstance(url, str):
            raise _unexpected("part URL list")
        urls[n] = Secret(url)
    return urls


def parse_plan(raw: object) -> Plan:
    fields = as_dict(raw)
    if fields is None:
        raise _unexpected("upload plan")
    no_direct = "part_urls" in fields and fields["part_urls"] is None
    part_size = _whole(fields.get("part_size_bytes"))
    total = _whole(fields.get("total_parts"))
    next_part = _whole(fields.get("next_part_number"))
    if (
        part_size is None
        or total is None
        or not 1 <= part_size <= MAX_PART_BYTES
        or total < 1
        or (next_part is not None and next_part < 1)
    ):
        raise _unexpected("upload plan")
    return Plan(
        part_size=part_size,
        total_parts=total,
        urls=_urls(fields.get("part_urls")),
        next_part=next_part,
        direct=not no_direct,
    )


def bad_part_plan() -> UploadError:
    return UploadError(
        "The API's upload plan does not describe the file's parts.", code="bad_part_plan"
    )


def parse_created(body: object) -> Created:
    fields = as_dict(body)
    job_id = None if fields is None else fields.get("job_id")
    if fields is None or not isinstance(job_id, str) or not usable_segment(job_id):
        raise _unexpected("create response")
    upload = fields.get("upload")
    state = fields.get("state")
    return Created(
        job_id=job_id,
        state=state if isinstance(state, str) else "uploading",
        plan=None if upload is None else parse_plan(upload),
    )


def plan_for(plan: Plan | None, size: int) -> Plan:
    """The plan the API gave, checked against the file; the 32 MiB cut when there is none."""
    if plan is None:
        return proxied_plan(size)
    if plan.total_parts != math.ceil(size / plan.part_size):
        raise bad_part_plan()
    return plan


def proxied_plan(size: int) -> Plan:
    return Plan(
        part_size=MAX_PART_BYTES,
        total_parts=max(1, math.ceil(size / MAX_PART_BYTES)),
        urls={},
        next_part=None,
    )


class UrlBook:
    """The presigned URLs fetched so far. A URL older than 23 h counts as missing (spec 8.4)."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._urls: dict[int, tuple[Secret, float]] = {}
        self.next_start: int | None = None

    def store(self, urls: dict[int, Secret], next_part: int | None) -> None:
        now = self._clock.now()
        for n, url in urls.items():
            self._urls[n] = (url, now)
        self.next_start = next_part

    def is_current(self, n: int, url: Secret) -> bool:
        """Whether `url` is still the one stored for part `n`."""
        entry = self._urls.get(n)
        return entry is not None and entry[0].reveal() == url.reveal()

    def get(self, n: int) -> Secret | None:
        entry = self._urls.get(n)
        if entry is None or self._clock.now() - entry[1] > URL_MAX_AGE:
            return None
        return entry[0]


class Action(enum.Enum):
    REFRESH = "refresh"
    FALLBACK = "fallback"
    EXHAUSTED = "exhausted"


@dataclass(slots=True)
class PartAttempts:
    expired_refreshes: int = 0
    rounds: int = 0


class Mode(enum.Enum):
    UNDECIDED = "undecided"
    DIRECT = "direct"
    PROXIED = "proxied"


@dataclass(slots=True)
class UploadState:
    """Which way the parts go and what has been acknowledged, shared by every part's worker.

    The way is one state under one lock: undecided, then direct (the first direct success) or
    proxied (the first part that gives up on direct), and never both. A direct success that
    arrives after the switch loses and its part is sent through the API again.
    """

    mode: Mode
    etags: dict[int, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def proxied(self) -> bool:
        return self.mode is Mode.PROXIED

    def record(self, n: int, etag: str) -> bool:
        """Notes a direct success; False when the upload went through the API in the meantime."""
        with self._lock:
            if self.mode is Mode.PROXIED:
                return False
            self.mode = Mode.DIRECT
            self.etags[n] = etag
            return True

    def fall_back(self) -> bool:
        """A part-urls page said direct upload is not available. True when the rest goes through
        the API now; False once a direct PUT has succeeded, which keeps the direct retries (spec
        8.4, Fallback rule)."""
        with self._lock:
            if self.mode is Mode.DIRECT:
                return False
            self.mode = Mode.PROXIED
            return True

    def decide(self, attempts: PartAttempts, status: int | None) -> Action:
        """What a part does after its direct PUT failed even with the transport's retries.

        An R2 403 means an expired URL: refresh it, once. Otherwise, while no direct PUT has
        succeeded, every remaining part goes through the API (the app's rule). After a success
        the part keeps trying direct: its retries, then a re-fetched URL and the retries again
        (spec 8.4), then `parts_exhausted`.
        """
        with self._lock:
            if self.mode is Mode.PROXIED:
                return Action.FALLBACK
            if status == HTTP_FORBIDDEN and attempts.expired_refreshes < 1:
                attempts.expired_refreshes += 1
                return Action.REFRESH
            if self.mode is Mode.UNDECIDED and attempts.rounds == 0:
                self.mode = Mode.PROXIED
                return Action.FALLBACK
            attempts.rounds += 1
            return Action.REFRESH if attempts.rounds == 1 else Action.EXHAUSTED

    def parts_body(self) -> dict[str, object] | None:
        """The body of `complete`: the sorted parts for a direct upload, none for a proxied one."""
        if self.mode is Mode.PROXIED:
            return None
        return {"parts": [{"n": n, "etag": self.etags[n]} for n in sorted(self.etags)]}


def first_mode(plan: Plan | None) -> Mode:
    return Mode.UNDECIDED if plan is not None and plan.direct else Mode.PROXIED


def exhausted(n: int) -> UploadError:
    return UploadError(
        f"Part {n} could not be uploaded after its retries and a fresh URL.", code=PARTS_EXHAUSTED
    )


def stream_size_mismatch() -> UploadError:
    return UploadError(
        "The stream did not hold the number of bytes that was declared.",
        code="stream_size_mismatch",
    )


def part_url_missing(n: int) -> UploadError:
    return UploadError(f"The API gave no upload URL for part {n}.", code="part_url_missing")


def etag_missing(n: int) -> UploadError:
    return UploadError(f"Storage accepted part {n} but sent no ETag.", code="etag_missing")


def source_read_failed(n: int, failure: BaseException) -> UploadError:
    return UploadError(
        f"Part {n} could not be read from the file ({failure}).", code="source_read_failed"
    )


def read_part(source: Source, plan: Plan, n: int) -> bytes:
    """The bytes of part `n`; a read that fails or comes up short is an upload error."""
    offset, length = part_range(plan, source.size, n)
    try:
        data = source.read_range(offset, length)
    except (OSError, ValueError) as failure:
        raise source_read_failed(n, failure) from failure
    if len(data) != length:
        raise short_read(n, source)
    return data


def short_read(n: int, source: Source) -> UploadError:
    if source.is_stream:
        return stream_size_mismatch()
    return UploadError(f"The file ended before part {n} was complete.", code="upload_incomplete")


def part_range(plan: Plan, size: int, n: int) -> tuple[int, int]:
    offset = (n - 1) * plan.part_size
    return offset, max(0, min(plan.part_size, size - offset))


def etag_of(response: httpx.Response) -> str | None:
    if not response.is_success:
        return None
    etag = response.headers.get("etag")
    return etag.strip('"') if etag else None


def r2_extensions(n: int) -> dict[str, object]:
    return {
        CLASS_EXTENSION: RetryClass.PART,
        LABEL_EXTENSION: f"r2:part/{n}",
        STREAM_EXTENSION: True,
    }


PART_TIMEOUTS: Final = httpx.Timeout(PART_TIMEOUT)


class SyncUploader:
    """Uploads the parts of one job on a thread pool: direct to R2, falling back to the API."""

    def __init__(
        self,
        session: SyncSession,
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
        self._pages = threading.Lock()
        self._width = 1 if source.sequential else concurrency

    def upload(self, on_bytes: Callable[[int], None], heartbeat: Heartbeat) -> None:
        total = self.plan.total_parts
        sent = 0
        numbers = iter(range(1, total + 1))
        pending: dict[Future[int], int] = {}
        with ThreadPoolExecutor(max_workers=self._width) as pool:
            try:
                while True:
                    while len(pending) < self._width and (n := next(numbers, None)) is not None:
                        pending[pool.submit(self._upload_part, n)] = n
                    if not pending:
                        break
                    done, _ = wait(list(pending), return_when=FIRST_COMPLETED)
                    for future in done:
                        del pending[future]
                        sent += future.result()
                    on_bytes(sent)
                    heartbeat.raise_if_failed()
            except BaseException:
                for future in pending:
                    future.cancel()
                raise

    def _read(self, n: int) -> bytes:
        return read_part(self._source, self.plan, n)

    def _upload_part(self, n: int) -> int:
        data = self._read(n)
        attempts = PartAttempts()
        while True:
            if self.state.proxied:
                self._put_proxied(n, data)
                return len(data)
            url = self._url_for(n)
            if url is None:
                continue
            status, etag = self._put_direct(n, url, data)
            if etag is not None:
                if not self.state.record(n, etag):
                    self._put_proxied(n, data)
                return len(data)
            action = self.state.decide(attempts, status)
            if action is Action.EXHAUSTED:
                raise exhausted(n)
            if action is Action.REFRESH:
                self._refresh(n, url)

    def _put_direct(self, n: int, url: Secret, data: bytes) -> tuple[int | None, str | None]:
        client = self._session.r2
        try:
            with hiding_signed_url(f"r2:part/{n}"):
                response = client.send(
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
                    response.close()
                finally:
                    release(response.request)
        except NetworkError:
            return None, None

    def _put_proxied(self, n: int, data: bytes) -> None:
        client = self._session.http
        response = client.send(
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
                response.read()
                raise_for_response(response, credentials=self._session.credentials)
        finally:
            try:
                response.close()
            finally:
                release(response.request)

    def _url_for(self, n: int) -> Secret | None:
        """The URL of part `n`; None when a page said the rest goes through the API."""
        with self._pages:
            url = self._book.get(n)
            if url is None:
                self._fetch_for(n)
                if self.state.proxied:
                    return None
                url = self._book.get(n)
            if url is None:
                raise part_url_missing(n)
            return url

    def _fetch_for(self, n: int) -> None:
        start = self._book.next_start
        if start is None or n < start:
            self._fetch(n, advance=False)
            return
        while (
            self._book.get(n) is None
            and self._book.next_start is not None
            and not self.state.proxied
        ):
            self._fetch(self._book.next_start, advance=True)

    def _refresh(self, n: int, failed_url: Secret) -> None:
        with self._pages:
            if self._book.is_current(n, failed_url):
                self._fetch(n, advance=False)

    def _fetch(self, start: int, *, advance: bool) -> None:
        """One `part-urls` page. The pages after the first come in order (`advance`); a refresh
        of an earlier page leaves the cursor of the pages still to come where it was."""
        response = self._session.http.get(
            f"/v1/uploads/{segment(self._job_id)}/part-urls", params={"start": start}
        )
        plan = parsed(response, self._session.credentials, parse_plan)
        if not plan.direct and self.state.fall_back():
            return
        cursor = plan.next_part if advance else self._book.next_start
        if advance and cursor is not None and cursor <= start:
            cursor = None
        self._book.store(plan.urls, cursor)
