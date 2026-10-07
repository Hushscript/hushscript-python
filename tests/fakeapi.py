"""An in-process stand-in for the API's upload, job and transcript routes, for the pipeline tests.

It follows the conformance mock where the pipeline can tell the difference: direct part URLs on
the API's own origin (so the R2 client must not send the token), exact Content-Length, unquoted
ETags, sorted `parts` in complete, a hold released at complete.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx

from helpers import BASE_URL

if TYPE_CHECKING:
    from collections.abc import Callable

Reply = httpx.Response | Exception | None
PAGE = 16
TRANSCRIPT = {
    "id": "tr_fake_0001",
    "title": "Fake",
    "language_detected": "en",
    "duration_seconds": 24,
    "body": {
        "original": {"utterances": [{"speaker": "A", "start_ms": 0, "end_ms": 900, "text": "Hi."}]}
    },
}


def error_reply(status: int, slug: str, code: int, **extra: object) -> httpx.Response:
    return httpx.Response(status, json={"error": slug, "code": code, **extra})


@dataclass
class Job:
    id: str
    size: int
    part_size: int | None
    total: int | None
    key: str | None
    parts: dict[int, tuple[str, int, bool]] = field(default_factory=dict)
    state: str = "uploading"
    polls: int = 0
    transcript_id: str | None = None


@dataclass
class FakeApi:
    parts: int = 3
    proxied: bool = False
    balance: int = 36000
    held: int = 0
    max_daily: int = 36000
    used_today: int = 0
    complete_state: str = "queued"
    processing_polls: int = 1
    failed: dict[str, str] | None = None
    drop_transcript_id: bool = False
    create_steps: list[Reply] = field(default_factory=list)
    r2_hook: Callable[[int, int], Reply] | None = None
    part_hook: Callable[[int, int], Reply] | None = None
    heartbeat_steps: list[Reply] = field(default_factory=list)
    url_ttl_expired: bool = False
    retain_bodies: bool = True
    r2_delay: float = 0.0
    overrides: list[tuple[str, str, Callable[[], httpx.Response]]] = field(default_factory=list)
    lose_parts: tuple[int, ...] = ()
    drop_after_commit: int = 0
    rate_limit_every: int = 0
    creates: int = 0
    heartbeat_seen: threading.Event = field(default_factory=threading.Event)
    requests: list[httpx.Request] = field(default_factory=list)
    jobs: dict[str, Job] = field(default_factory=dict)
    keys: dict[str, str] = field(default_factory=dict)
    r2_calls: dict[int, int] = field(default_factory=dict)
    part_calls: dict[int, int] = field(default_factory=dict)
    direct_successes: int = 0
    now: Callable[[], float] = lambda: 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def sync(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def asynchronous(self) -> httpx.MockTransport:
        async def handler(request: httpx.Request) -> httpx.Response:
            if self.r2_delay and request.url.path.startswith("/__r2/"):
                await asyncio.sleep(self.r2_delay)
            return self._handle(request)

        return httpx.MockTransport(handler)

    def count(self, method: str, pattern: str) -> int:
        return sum(
            1
            for request in self.requests
            if request.method == method and re.fullmatch(pattern, request.url.path)
        )

    def of(self, method: str, pattern: str) -> list[httpx.Request]:
        return [
            r for r in self.requests if r.method == method and re.fullmatch(pattern, r.url.path)
        ]

    def _handle(self, request: httpx.Request) -> httpx.Response:  # noqa: C901, PLR0911
        with self.lock:
            # The pipeline lets go of a part's bytes once it is sent, so the record keeps its own.
            self.requests.append(
                httpx.Request(
                    request.method,
                    request.url,
                    headers=request.headers,
                    content=request.content if self.retain_bodies else b"",
                )
            )
        path = request.url.path
        method = request.method
        for want_method, pattern, build in self.overrides:
            if method == want_method and re.fullmatch(pattern, path):
                return build()
        if method == "GET" and path == "/v1/account":
            return self._account()
        if method == "POST" and path == "/v1/uploads":
            return self._create(request)
        if match := re.fullmatch(r"/v1/uploads/([^/]+)/part-urls", path):
            return self._part_urls(match[1], int(request.url.params.get("start", "1")))
        if match := re.fullmatch(r"/__r2/([^/]+)/(\d+)", path):
            return self._r2(request, match[1], int(match[2]))
        if match := re.fullmatch(r"/v1/uploads/([^/]+)/parts/(\d+)", path):
            return self._part(request, match[1], int(match[2]))
        if match := re.fullmatch(r"/v1/uploads/([^/]+)/heartbeat", path):
            return self._heartbeat(match[1])
        if match := re.fullmatch(r"/v1/uploads/([^/]+)/complete", path):
            return self._complete(request, match[1])
        if match := re.fullmatch(r"/v1/jobs/([^/]+)", path):
            return self._job(match[1])
        if match := re.fullmatch(r"/v1/transcripts/([^/]+)", path):
            return httpx.Response(200, json={**TRANSCRIPT, "id": match[1]})
        return error_reply(404, "not_found", 1000)

    def _account(self) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "balance_seconds": self.balance,
                "held_seconds": self.held,
                "limits": {
                    "max_daily_seconds": self.max_daily,
                    "used_today_seconds": self.used_today,
                },
            },
        )

    def _page(self, job: Job, start: int, *, expired: bool = False) -> dict[str, object]:
        total = job.total or 0
        sig = "expired" if expired else "ok"
        urls = [
            {"n": n, "url": f"{BASE_URL}/__r2/{job.id}/{n}?sig={sig}"}
            for n in range(start, min(start + PAGE, total + 1))
        ]
        nxt = start + PAGE if start + PAGE <= total else None
        return {
            "part_size_bytes": job.part_size,
            "total_parts": total,
            "part_urls": urls,
            "next_part_number": nxt,
        }

    def _create(self, request: httpx.Request) -> httpx.Response:
        with self.lock:
            self.creates += 1
            if self.rate_limit_every and self.creates % self.rate_limit_every == 0:
                return error_reply(429, "rate_limited", 5000)
            step = self.create_steps.pop(0) if self.create_steps else None
        if isinstance(step, Exception):
            raise step
        if step is not None:
            return step
        body = json.loads(request.content)
        key = body.get("idempotency_key")
        with self.lock:
            existing = self.keys.get(key) if key else None
            if existing is not None:
                job = self.jobs[existing]
            else:
                size = body["size_bytes"]
                part = None if self.proxied else max(1, math.ceil(size / self.parts))
                total = None if part is None else math.ceil(size / part)
                job = Job(f"job_{len(self.jobs) + 1}", size, part, total, key)
                self.jobs[job.id] = job
                if key:
                    self.keys[key] = job.id
        direct = not self.proxied and job.state == "uploading"
        if self.drop_after_commit > 0:
            self.drop_after_commit -= 1
            raise httpx.ReadError("connection reset after the job was committed")
        return httpx.Response(
            200,
            json={
                "job_id": job.id,
                "state": job.state,
                "upload": self._page(job, 1, expired=self.url_ttl_expired) if direct else None,
            },
        )

    def _job_or_404(self, job_id: str) -> Job | httpx.Response:
        return self.jobs.get(job_id) or error_reply(404, "not_found", 1000)

    def _part_urls(self, job_id: str, start: int) -> httpx.Response:
        job = self._job_or_404(job_id)
        if isinstance(job, httpx.Response):
            return job
        return httpx.Response(200, json=self._page(job, start))

    def _r2(self, request: httpx.Request, job_id: str, n: int) -> httpx.Response:
        job = self.jobs[job_id]
        with self.lock:
            self.r2_calls[n] = self.r2_calls.get(n, 0) + 1
            attempt = self.r2_calls[n]
        if "authorization" in request.headers:
            return httpx.Response(400, text="auth header on a signed url")
        if request.url.params.get("sig") == "expired":
            return httpx.Response(403, text="expired")
        if self.r2_hook is not None:
            step = self.r2_hook(n, attempt)
            if isinstance(step, Exception):
                raise step
            if step is not None:
                return step
        data = request.content
        if int(request.headers["content-length"]) != len(data):
            return httpx.Response(400, text="bad content-length")
        digest = hashlib.md5(data, usedforsecurity=False).hexdigest()
        with self.lock:
            if n not in self.lose_parts:
                job.parts[n] = (digest, len(data), True)
            self.direct_successes += 1
        return httpx.Response(200, headers={"ETag": f'"{digest}"'})

    def _part(self, request: httpx.Request, job_id: str, n: int) -> httpx.Response:
        job = self.jobs[job_id]
        with self.lock:
            self.part_calls[n] = self.part_calls.get(n, 0) + 1
            attempt = self.part_calls[n]
        if self.part_hook is not None:
            step = self.part_hook(n, attempt)
            if isinstance(step, Exception):
                raise step
            if step is not None:
                return step
        digest = hashlib.md5(request.content, usedforsecurity=False).hexdigest()
        with self.lock:
            job.parts[n] = (digest, len(request.content), False)
        return httpx.Response(200, json={"ok": True, "part": n})

    def _heartbeat(self, job_id: str) -> httpx.Response:
        self.heartbeat_seen.set()
        with self.lock:
            step = self.heartbeat_steps.pop(0) if self.heartbeat_steps else None
        if isinstance(step, Exception):
            raise step
        if step is not None:
            return step
        job = self.jobs[job_id]
        if job.state != "uploading":
            return error_reply(409, "wrong_state", 4001)
        return httpx.Response(200, json={"ok": True})

    def _complete(self, request: httpx.Request, job_id: str) -> httpx.Response:
        job = self.jobs[job_id]
        listed = json.loads(request.content).get("parts") if request.content else None
        direct = {n for n, (_, _, via_direct) in job.parts.items() if via_direct}
        total = job.total or math.ceil(job.size / (32 * 1024 * 1024))
        ok = sorted(job.parts) == list(range(1, total + 1)) and (
            (listed is None and not direct)
            or (
                listed is not None
                and [p["n"] for p in listed] == sorted(direct)
                and all(job.parts[p["n"]][0] == p["etag"] for p in listed)
            )
        )
        if not ok:
            job.state = "failed"
            return error_reply(422, "upload_incomplete", 1041)
        job.state = self.complete_state
        if job.state == "done":
            job.transcript_id = f"tr_{job.id}"
        return httpx.Response(200, json={"ok": True, "state": job.state})

    def _job(self, job_id: str) -> httpx.Response:
        job = self.jobs.get(job_id)
        if job is None:
            return error_reply(404, "not_found", 1000)
        if job.state not in {"uploading", "done", "failed"}:
            job.polls += 1
            if self.failed is not None and job.polls > self.processing_polls:
                job.state = "failed"
            elif job.polls > self.processing_polls:
                job.state = "done"
                job.transcript_id = f"tr_{job.id}"
        failed = self.failed if job.state == "failed" and self.failed else {}
        return httpx.Response(
            200,
            json={
                "id": job.id,
                "state": job.state,
                "transcript_id": None if self.drop_transcript_id else job.transcript_id,
                "error": failed.get("error"),
                "failure_kind": failed.get("failure_kind"),
            },
        )
