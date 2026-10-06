"""Runs the conformance scenarios against the mock (the conformance repo's runner contract).

Only the ops in OPS are mapped so far. A scenario that needs any other op is reported as SKIP and
does not fail the run; CONFORMANCE_STRICT=1 turns every skip into a failure, which is what the
runner contract asks for once the friendly layer is complete.
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from typing import TYPE_CHECKING, Any

import httpx

import hushscript
from hushscript import Hushscript, HushscriptError
from hushscript._json import as_dict, as_list

BASE_URL = "http://127.0.0.1:4010"
TEST_TOKEN = "hsr1:eu:pat." + "0123456789abcdef" * 2 + "." + "fedcba9876543210" * 4

if TYPE_CHECKING:
    from collections.abc import Callable

Json = Any


class VirtualClock:
    """Time that moves only when the SDK sleeps; the mock's clock is moved by the same amount."""

    def __init__(self, control: httpx.Client) -> None:
        self._control = control
        self.time = 0.0

    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._control.post("/__clock", json={"advance": seconds}).raise_for_status()
            self.time += seconds

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


def _balance(hs: Hushscript, _args: Json) -> Json:
    balance = hs.balance()
    return {
        "seconds": balance.seconds,
        "minutes": balance.minutes,
        "heldSeconds": balance.held_seconds,
        "expiresAt": None if balance.expires_at is None else balance.expires_at.isoformat(),
    }


OPS: dict[str, Callable[[Hushscript, Json], Json]] = {"balance": _balance}


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
        klass = getattr(hushscript, class_name, None)
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
    ops = [call["op"]]
    if "prior" in call:
        ops.append(call["prior"]["op"])
    return [op for op in ops if op not in OPS]


def run_scenario(control: httpx.Client, name: str) -> tuple[str, str]:
    scenario = control.get(f"/__files/scenarios/{name}.json").raise_for_status().json()
    call = scenario["call"]
    missing = unmapped_ops(call)
    if missing:
        return "SKIP", f"op {', '.join(missing)} is not mapped yet"
    control.post("/__scenario", json={"name": name}).raise_for_status()
    clock = VirtualClock(control)
    hs = Hushscript(TEST_TOKEN, base_url=BASE_URL, clock=clock)
    control.post("/__mark").raise_for_status()
    expect = scenario["expect"]
    problems: list[str] = []
    try:
        result = OPS[call["op"]](hs, call.get("args", {}))
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
    with httpx.Client(base_url=BASE_URL, timeout=30) as control:
        names = control.get("/__scenarios").raise_for_status().json()["scenarios"]
        if not names:
            print("the mock lists no scenarios", file=sys.stderr)
            return 1
        for name in names:
            status, reason = run_scenario(control, name)
            if status == "SKIP" and strict:
                status, reason = "FAIL", f"skipped in strict mode: {reason}"
            counts[status] += 1
            print(f"{status} {name}" + (f": {reason}" if reason else ""))
    print(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    return 1 if counts["FAIL"] or counts["PASS"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
