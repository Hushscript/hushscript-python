"""Runs the conformance scenarios against the mock (the conformance repo's runner contract).

Only the ops in OPS are mapped so far. A scenario that needs any other op is reported as SKIP and
does not fail the run; CONFORMANCE_STRICT=1 turns every skip into a failure, which is what the
runner contract asks for once the friendly layer is complete.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

import golden_table
import httpx

import hushscript
import hushscript._client as client_module
from hushscript import Hushscript, HushscriptError
from hushscript._json import as_dict, as_list
from hushscript.transcribe.probe import probe_duration
from hushscript.transcribe.sniff import sniff
from hushscript.transcribe.source import make_source
from hushscript.transcript import Transcript

BASE_URL = "http://127.0.0.1:4010"
TEST_TOKEN = "hsr1:eu:pat." + "0123456789abcdef" * 2 + "." + "fedcba9876543210" * 4

if TYPE_CHECKING:
    from collections.abc import Callable

Json = Any

# Scenarios of the pinned conformance tag still name the spec 9.2 class PermissionError (R12 renamed
# it PermissionDeniedError); drop this once the pin moves past the rename.
CLASS_ALIASES = {"PermissionError": "PermissionDeniedError"}


class Timer:
    def __init__(self, due: float) -> None:
        self.due = due
        self.fired = threading.Event()


class VirtualClock:
    """Time that moves only when the driver says so (runner contract section 5).

    `sleep` registers a timer and blocks until the driver fires it, so the SDK's waits are visible
    to the driver and a wait that nobody ends is a stall, not a hang.
    """

    def __init__(self) -> None:
        self.time = 0.0
        self.registered = 0
        self._timers: list[Timer] = []
        self._lock = threading.Lock()

    def now(self) -> float:
        return self.time

    def _register(self, seconds: float) -> Timer:
        with self._lock:
            timer = Timer(self.time + seconds)
            self._timers.append(timer)
            self.registered += 1
            return timer

    def _drop(self, timer: Timer) -> None:
        with self._lock:
            if timer in self._timers:
                self._timers.remove(timer)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._register(seconds).fired.wait()

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        if stop.is_set():
            return True
        timer = self._register(seconds)
        while not timer.fired.wait(0.005):
            if stop.is_set():
                self._drop(timer)
                return True
        return stop.is_set()

    async def asleep(self, seconds: float) -> None:
        await asyncio.to_thread(self.sleep, seconds)

    def earliest(self) -> float | None:
        with self._lock:
            return min((timer.due for timer in self._timers), default=None)

    def advance_to(self, target: float) -> None:
        self.time = max(self.time, target)

    def fire_due(self) -> None:
        with self._lock:
            due = [timer for timer in self._timers if timer.due <= self.time]
            self._timers = [timer for timer in self._timers if timer.due > self.time]
        for timer in due:
            timer.fired.set()


class InFlight:
    """Requests the SDK has sent and not yet had an answer to, counted under its transport."""

    def __init__(self) -> None:
        self.value = 0
        self.total = 0
        self._lock = threading.Lock()

    def enter(self) -> None:
        with self._lock:
            self.value += 1
            self.total += 1

    def leave(self) -> None:
        with self._lock:
            self.value -= 1


class CountingTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport, counter: InFlight) -> None:
        self._inner = inner
        self._counter = counter

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self._counter.enter()
        try:
            return self._inner.handle_request(request)
        finally:
            self._counter.leave()

    def close(self) -> None:
        self._inner.close()


SETTLE_SECONDS = 0.02
STALL_SECONDS = 0.5


class SDKStalledError(Exception):
    """The call is pending and nothing it could be waiting for exists."""


class Driver:
    """Moves the virtual clock and the mock's while the SDK's call runs (runner contract 5)."""

    def __init__(self, control: httpx.Client, clock: VirtualClock, counter: InFlight) -> None:
        self.control = control
        self.clock = clock
        self.counter = counter

    def _state(self) -> Json:
        return self.control.get("/__state").raise_for_status().json()

    def _settle(self, done: threading.Event) -> bool:
        """True once the SDK has been quiet for the settle period; False if the call finished."""
        started = time.monotonic()
        seen = self.clock.registered
        while time.monotonic() - started < SETTLE_SECONDS:
            if done.is_set():
                return False
            held = self._state()["pendingHolds"]
            if self.counter.value - held != 0 or self.clock.registered != seen:
                started = time.monotonic()
                seen = self.clock.registered
            time.sleep(0.002)
        return True

    def drive(self, done: threading.Event) -> None:
        idle_since: float | None = None
        activity = (self.clock.registered, self.counter.total)
        while not done.is_set():
            if not self._settle(done):
                return
            state = self._state()
            targets = [
                target
                for target in (self.clock.earliest(), state["nextHoldAt"])
                if target is not None
            ]
            now_activity = (self.clock.registered, self.counter.total)
            if not targets:
                if idle_since is None or now_activity != activity:
                    idle_since = time.monotonic()
                    activity = now_activity
                elif time.monotonic() - idle_since >= STALL_SECONDS and self.counter.value == 0:
                    raise SDKStalledError
                continue
            idle_since = None
            target = min(targets)
            if target > self.clock.time:
                advance = target - self.clock.time
                self.control.post("/__clock", json={"advance": advance}).raise_for_status()
                self.clock.advance_to(target)
                # Held responses first: let the SDK take them in before timers at the same instant.
                if not self._settle(done):
                    return
            self.clock.fire_due()

    def run(self, call: Callable[[], Json]) -> Json:
        done = threading.Event()
        outcome: list[Json] = []
        failure: list[BaseException] = []

        def target() -> None:
            try:
                outcome.append(call())
            except BaseException as error:  # noqa: BLE001  # handed to the caller below
                failure.append(error)
            finally:
                done.set()

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        self.drive(done)
        worker.join()
        if failure:
            raise failure[0]
        return outcome[0]


def _balance(hs: Hushscript, _args: Json, _files: Files) -> Json:
    balance = hs.balance()
    return {
        "seconds": balance.seconds,
        "minutes": balance.minutes,
        "heldSeconds": balance.held_seconds,
        "expiresAt": None if balance.expires_at is None else balance.expires_at.isoformat(),
    }


def _transcript_result(raw: Json, text: str) -> Json:
    utterances = raw.get("body", {}).get("original", {}).get("utterances", [])
    return {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "language": raw.get("language_detected"),
        "durationSeconds": raw.get("duration_seconds"),
        "utteranceCount": len(utterances),
        "text": text,
        "raw": raw,
    }


def _options(args: Json) -> Json:
    return {_snake(key): value for key, value in args.get("options", {}).items()}


def _transcribe(hs: Hushscript, args: Json, files: Files) -> Json:
    transcript = hs.transcribe(str(files[args["file"]]), **_options(args))
    return _transcript_result(dict(transcript.to_json()), transcript.text)


def _probe(_hs: Hushscript, args: Json, files: Files) -> Json:
    tolerance = args["toleranceSeconds"]
    refuse = set(args.get("refuse", []))
    failures: list[Json] = []
    refused = 0
    for name, expected in files.durations.items():
        source = make_source(files[name])
        if name in refuse:
            # R46: the sniffer turns these away before any probe runs, as `check_media` does.
            if sniff(source.head()) is None:
                refused += 1
            else:
                failures.append({"file": name, "expected": "refused", "got": "sniffed"})
            continue
        try:
            got: float | None = probe_duration(source)
        except HushscriptError:
            got = None
        if got is None or abs(got - expected) > tolerance:
            failures.append({"file": name, "expected": expected, "got": got})
    return {
        "checked": len(files.durations) - len(refuse),
        "refused": refused,
        "failures": failures,
    }


def _list_transcripts(hs: Hushscript, args: Json, _files: Files) -> Json:
    page_size = args.get("pageSize")
    rows = list(hs.transcripts.list(page_size=page_size))
    return {
        "count": len(rows),
        "firstId": rows[0].id if rows else None,
        "lastId": rows[-1].id if rows else None,
    }


def _get_transcript(hs: Hushscript, args: Json, _files: Files) -> Json:
    transcript = hs.transcripts.get(args["id"])
    return _transcript_result(dict(transcript.to_json()), transcript.text)


def _format(_hs: Hushscript, _args: Json, files: Files) -> Json:
    """Every golden rendered from its transcript fixture; a mismatch is the golden's file name.
    The files come from the mock and the SDK sends no request."""
    goldens = golden_table.all_goldens()
    mismatches: list[str] = []
    for golden in goldens:
        transcript = Transcript.from_api(
            json.loads(files.text(f"transcripts/{golden.transcript}.json"))
        )
        if golden.render(transcript) != files.text(f"exports/{golden.file}"):
            mismatches.append(golden.file)
    return {"checked": len(goldens), "mismatches": mismatches}


OPS: dict[str, Callable[[Hushscript, Json, Files], Json]] = {
    "balance": _balance,
    "listTranscripts": _list_transcripts,
    "getTranscript": _get_transcript,
    "format": _format,
    "transcribe": _transcribe,
    "probe": _probe,
}


class Files:
    """The media a scenario names, downloaded from the mock into a scratch directory."""

    def __init__(self, control: httpx.Client, root: Path) -> None:
        self._control = control
        self._root = root
        self.durations: dict[str, float] = {}

    def fetch(self, name: str) -> Path:
        path = self._root / name
        if not path.exists():
            body = self._control.get(f"/__files/fixtures/{name}").raise_for_status().content
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        return path

    def text(self, name: str) -> str:
        """A fixture file as text, with its line endings exactly as stored."""
        body = self._control.get(f"/__files/fixtures/{name}").raise_for_status().content
        return body.decode("utf-8")

    def __getitem__(self, name: str) -> Path:
        return self.fetch(name if "/" in name else f"media/{name}")

    def prepare(self, call: Json) -> None:
        for step in (call.get("prior"), call):
            if step is not None and "file" in step.get("args", {}):
                self.fetch(step["args"]["file"])
        if call["op"] == "probe":
            listing = self._control.get("/__files/fixtures/media/durations.json")
            self.durations = listing.raise_for_status().json()
            for name in self.durations:
                self.fetch(f"media/{name}")


def _snake(key: str) -> str:
    return re.sub(r"([A-Z])", lambda match: "_" + match.group(1).lower(), key)


def subset(expected: Json, actual: Json, path: str = "result") -> list[str]:
    wanted = as_dict(expected)
    if wanted is not None:
        got = as_dict(actual)
        if got is None:
            return [f"{path}: expected an object, got {actual!r}"]
        problems: list[str] = []
        for key, value in wanted.items():
            if key not in got:
                problems.append(f"{path}.{key}: missing")
            else:
                problems += subset(value, got[key], f"{path}.{key}")
        return problems
    wanted_list = as_list(expected)
    if wanted_list is not None:
        got_list = as_list(actual)
        if got_list is None or len(got_list) != len(wanted_list):
            return [f"{path}: expected {expected!r}, got {actual!r}"]
        pairs = zip(wanted_list, got_list, strict=True)
        return [p for i, (e, a) in enumerate(pairs) for p in subset(e, a, f"{path}[{i}]")]
    return [] if expected == actual else [f"{path}: expected {expected!r}, got {actual!r}"]


def _surface(error: BaseException) -> str:
    parts = [str(error), repr(error)]
    if isinstance(error, HushscriptError):
        parts += [error.message, error.hint or "", repr(error.details)]
    cause = error.__cause__
    while cause is not None:
        parts += [str(cause), repr(cause)]
        cause = cause.__cause__
    return "\n".join(parts)


def _check_fields(expected: Json, error: HushscriptError) -> list[str]:
    problems: list[str] = []
    for key, attribute in (("code", "code"), ("numericCode", "numeric_code"), ("status", "status")):
        if key in expected and getattr(error, attribute) != expected[key]:
            problems.append(f"{key}: expected {expected[key]!r}, got {getattr(error, attribute)!r}")
    if "retryAfter" in expected and error.retry_after != expected["retryAfter"]:
        wanted = expected["retryAfter"]
        problems.append(f"retryAfter: expected {wanted!r}, got {error.retry_after!r}")
    if "hintContains" in expected and expected["hintContains"] not in (error.hint or ""):
        problems.append(f"hint {error.hint!r} does not contain {expected['hintContains']!r}")
    for name, value in expected.get("fields", {}).items():
        actual = getattr(error, _snake(name), None)
        present = bool(actual) if value == "<present>" else actual == value
        if not present:
            problems.append(f"fields.{name}: expected {value!r}, got {actual!r}")
    return problems


def check_error(expected: Json, error: BaseException) -> list[str]:
    if not isinstance(error, HushscriptError):
        return [f"expected an SDK error, got {type(error).__name__}: {error}"]
    problems = _check_fields(expected, error)
    class_name = expected.get("class")
    if class_name is not None:
        wanted_class: str = CLASS_ALIASES.get(class_name) or class_name
        klass = getattr(hushscript, wanted_class, None)
        if klass is None or not isinstance(error, klass):
            problems.append(f"class: expected {class_name}, got {type(error).__name__}")
    if "details" in expected:
        wanted = {_snake(key): value for key, value in expected["details"].items()}
        problems += subset(wanted, error.details, "details")
    surface = _surface(error)
    for text in expected.get("messageExcludes", []):
        needle = TEST_TOKEN if text == "$TOKEN" else text
        if needle in surface:
            problems.append(f"the error surface contains {text!r}")
    return problems


def unmapped_ops(call: Json) -> list[str]:
    mapped = {*OPS, "resume"}
    ops = [call["op"]]
    if "prior" in call:
        ops.append(call["prior"]["op"])
    return [op for op in ops if op not in mapped]


def _call(hs: Hushscript, call: Json, files: Files, token: str | None) -> Json:
    if call["op"] == "resume":
        return _resume(hs, call, files, token)
    return OPS[call["op"]](hs, call.get("args", {}), files)


def _resume(hs: Hushscript, call: Json, files: Files, token: str | None) -> Json:
    transcript = hs.resume(token or "", str(files[call["args"]["file"]]))
    return _transcript_result(dict(transcript.to_json()), transcript.text)


def run_scenario(  # noqa: C901
    control: httpx.Client, name: str, scratch: Path, counter: InFlight
) -> tuple[str, str]:
    scenario = control.get(f"/__files/scenarios/{name}.json").raise_for_status().json()
    call = scenario["call"]
    missing = unmapped_ops(call)
    if missing:
        return "SKIP", f"op {', '.join(missing)} is not mapped yet"
    files = Files(control, scratch)
    files.prepare(call)
    control.post("/__scenario", json={"name": name}).raise_for_status()
    clock = VirtualClock()
    counter.value = 0
    driver = Driver(control, clock, counter)
    hs = Hushscript(TEST_TOKEN, base_url=BASE_URL, clock=clock)
    expect = scenario["expect"]
    problems: list[str] = []
    token: str | None = None
    try:
        prior = call.get("prior")
        if prior is not None:
            try:
                driver.run(lambda: OPS[prior["op"]](hs, prior.get("args", {}), files))
            except Exception as error:  # noqa: BLE001  # the prior call is meant to fail
                problems += check_error(prior["expectError"], error)
                token = getattr(error, "resume_token", None)
            else:
                problems.append("the prior call returned; it should have failed")
        control.post("/__mark").raise_for_status()
        result = driver.run(lambda: _call(hs, call, files, token))
    except SDKStalledError:
        problems.append("SDK stalled")
    except Exception as error:  # noqa: BLE001  # every failure is compared with the expectation
        if "error" in expect:
            problems += check_error(expect["error"], error)
        else:
            problems.append(f"raised {type(error).__name__}: {error}\n{traceback.format_exc()}")
    else:
        if "error" in expect:
            problems.append("expected an error, the call returned")
        elif "result" in expect:
            problems += subset(expect["result"], result)
    finally:
        hs.close()
    verdict = control.get("/__verify").raise_for_status().json()
    problems += [f"mock: {failure}" for failure in verdict["failures"]]
    return ("FAIL", "; ".join(problems)) if problems else ("PASS", "")


def main() -> int:
    strict = os.environ.get("CONFORMANCE_STRICT") == "1"
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    counter = InFlight()
    client_module._sync_inner = lambda: CountingTransport(  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        httpx.HTTPTransport(), counter
    )
    with (
        httpx.Client(base_url=BASE_URL, timeout=30) as control,
        tempfile.TemporaryDirectory() as tmp,
    ):
        names = control.get("/__scenarios").raise_for_status().json()["scenarios"]
        if not names:
            print("the mock lists no scenarios", file=sys.stderr)
            return 1
        for name in names:
            status, reason = run_scenario(control, name, Path(tmp), counter)
            if status == "SKIP" and strict:
                status, reason = "FAIL", f"skipped in strict mode: {reason}"
            counts[status] += 1
            print(f"{status} {name}" + (f": {reason}" if reason else ""))
    print(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    return 1 if counts["FAIL"] or counts["PASS"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
