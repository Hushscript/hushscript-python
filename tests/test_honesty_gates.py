from __future__ import annotations

import asyncio
import json
import os
import re
import runpy
import subprocess
import sys
import threading
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest
import runner

import hushscript._client as client_module

if TYPE_CHECKING:
    from collections.abc import Callable

    from hushscript import AsyncHushscript

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ({"killed": 0, "survived": 0}, 1),
        ({"killed": 8, "survived": 2, "total": 10}, 0),
        ({"killed": 7, "survived": 3, "total": 10}, 1),
    ],
)
def test_mutation_score_rejects_empty_runs_and_preserves_the_floor(
    counts: dict[str, int],
    expected: int,
    tmp_path: Path,
) -> None:
    stats = tmp_path / "stats.json"
    stats.write_text(json.dumps(counts), encoding="utf-8")
    main = cast(
        "Callable[[str], int]", runpy.run_path(str(ROOT / "scripts/check_mutation.py"))["main"]
    )
    assert main(str(stats)) == expected


@pytest.mark.parametrize(
    "status",
    [
        "survived",
        "timeout",
        "suspicious",
        "no_tests",
        "skipped",
        "segfault",
        "check_was_interrupted_by_user",
        "future_status",
    ],
)
@pytest.mark.parametrize("reported_total", [False, True])
def test_every_non_killed_mutant_counts_against_the_score(
    status: str,
    *,
    reported_total: bool,
    tmp_path: Path,
) -> None:
    counts = {"killed": 8, "survived": 0, status: 3}
    if reported_total:
        counts["total"] = 11
    stats = tmp_path / "stats.json"
    stats.write_text(json.dumps(counts), encoding="utf-8")
    main = cast(
        "Callable[[str], int]", runpy.run_path(str(ROOT / "scripts/check_mutation.py"))["main"]
    )
    assert main(str(stats)) == 1


def test_coverage_excludes_only_bare_ellipsis_bodies() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expressions = config["tool"]["coverage"]["report"]["exclude_also"]
    assert any(re.search(pattern, "    ...") for pattern in expressions)
    for line in ("def f(*args: tuple[str, ...]) -> None:", "value = (...,)", "# ..."):
        assert not any(re.search(pattern, line) for pattern in expressions), line


def test_mutation_targets_include_transcription_and_billing() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    paths = config["tool"]["mutmut"]["source_paths"]
    targets = {
        file.relative_to(ROOT).as_posix()
        for path in paths
        for file in ((ROOT / path).rglob("*.py") if (ROOT / path).is_dir() else [ROOT / path])
    }
    required = {
        "src/hushscript/_http.py",
        "src/hushscript/_retry.py",
        "src/hushscript/_pacing.py",
        "src/hushscript/resources/billing.py",
        *(
            file.relative_to(ROOT).as_posix()
            for file in (ROOT / "src/hushscript/transcribe").glob("*.py")
        ),
    }
    assert required <= targets
    assert config["tool"]["mutmut"]["pytest_add_cli_args_test_selection"] == ["tests/"]


def test_mutation_recipe_mounts_the_fixtures_its_tests_require(tmp_path: Path) -> None:
    justfile = (ROOT / "justfile").read_text(encoding="utf-8")
    anchor = "\nmutation version=floor:\n"
    boundary = "\nconformance version=floor:\n"
    assert justfile.count(anchor) == 1
    assert justfile.count(boundary) == 1
    recipe = justfile.split(anchor)[1].split(boundary)[0]
    script = "\n".join(
        line.removeprefix("    ") for line in recipe.splitlines() if "{{" not in line
    )
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    log = tmp_path / "calls.jsonl"
    recorder = tmp_path / "record_docker.py"
    recorder.write_text(
        "import json, os, sys\n"
        "with open(os.environ['TASK_DOCKER_LOG'], 'a') as output:\n"
        " output.write(json.dumps(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    # A shell function, not an executable on PATH: the test container mounts /tmp noexec.
    stub = 'docker() { "$TASK_PYTHON" "$TASK_DOCKER_RECORDER" "$@"; }\n'
    env = dict(
        os.environ,
        CONFORMANCE_DIR=str(fixtures),
        TASK_DOCKER_LOG=str(log),
        TASK_DOCKER_RECORDER=str(recorder),
        TASK_PYTHON=sys.executable,
    )
    subprocess.run(  # noqa: S603  # Only the local recording stub can receive Docker calls.
        ["bash", "-euo", "pipefail", "-c", stub + script],  # noqa: S607
        env=env,
        check=True,
    )
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [
        "compose",
        "run",
        "--rm",
        "-v",
        f"{fixtures}:/conformance:ro",
        "-e",
        "CONFORMANCE_DIR=/conformance",
        "mutation",
    ] in calls


def test_conformance_runs_both_clients_and_fails_async_skips_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passes: list[bool] = []

    def scenario(*_args: object, asynchronous: bool = False) -> tuple[str, str]:
        passes.append(asynchronous)
        return ("SKIP", "missing async op") if asynchronous else ("PASS", "")

    def control(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/__scenarios"
        return httpx.Response(200, json={"scenarios": ["one"]})

    original_client = httpx.Client

    def control_client(**kwargs: Any) -> httpx.Client:
        return original_client(transport=httpx.MockTransport(control), **kwargs)

    monkeypatch.setenv("CONFORMANCE_STRICT", "1")
    monkeypatch.setattr(runner, "run_scenario", scenario)
    monkeypatch.setattr(client_module, "_sync_inner", client_module._sync_inner)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(client_module, "_async_inner", client_module._async_inner)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(runner.Attempt, "begin", runner.Attempt.begin)
    monkeypatch.setattr(
        httpx,
        "Client",
        control_client,
    )
    assert runner.main() == 1
    assert passes == [False, True]


@pytest.mark.anyio
async def test_a_sync_only_op_is_rejected_by_the_async_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    op = "syncOnly"
    monkeypatch.setitem(runner.OPS, op, runner.OPS["format"])
    call: dict[str, Any] = {"op": op, "args": {}}
    assert runner.unmapped_ops(call) == []
    assert runner.unmapped_ops(call, asynchronous=True) == [op]

    def control(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/__files/scenarios/sync-only.json"
        return httpx.Response(200, json={"call": call})

    with httpx.Client(base_url=runner.BASE_URL, transport=httpx.MockTransport(control)) as client:
        status, detail = runner.run_scenario(
            client, "sync-only", tmp_path, runner.InFlight(), asynchronous=True
        )
        assert status == "SKIP"
        assert op in detail
        files = runner.Files(client, tmp_path)
        with pytest.raises(ValueError, match="unknown async op: syncOnly"):
            await runner._async_call(  # pyright: ignore[reportPrivateUsage]
                cast("AsyncHushscript", None), call, files, None
            )


@pytest.mark.anyio
async def test_virtual_clock_cancellation_drops_the_pending_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = runner.VirtualClock()
    started = threading.Event()
    register = clock._register  # pyright: ignore[reportPrivateUsage]

    def registered(seconds: float) -> runner.Timer:
        timer = register(seconds)
        started.set()
        return timer

    monkeypatch.setattr(clock, "_register", registered)
    task = asyncio.create_task(clock.asleep(120))
    try:
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert clock.earliest() is None
    finally:
        clock.advance_to(120)
        clock.fire_due()


@pytest.mark.parametrize("job", ["mutation", "fuzz"])
def test_nightly_jobs_check_out_their_pinned_conformance_fixtures(job: str) -> None:
    workflow = (ROOT / ".github/workflows/nightly.yml").read_text(encoding="utf-8")
    workflow = re.sub(r"(?m)\s+#.*$", "", workflow)
    anchor = f"\n  {job}:\n"
    assert workflow.count(anchor) == 1
    remaining = workflow.split(anchor)[1]
    boundary = re.search(r"\n  [a-z-]+:\n", remaining)
    block = remaining[: boundary.start()] if boundary else remaining
    steps = re.split(r"\n      - name: ", block)[1:]
    checkouts = [step for step in steps if "uses: actions/checkout@" in step]
    assert len(checkouts) == 2
    sdk, conformance = checkouts
    assert re.search(r"^          path: sdk$", sdk, re.MULTILINE)
    assert re.search(
        r"^          repository: Hushscript/hushscript-sdk-conformance$",
        conformance,
        re.MULTILINE,
    )
    assert re.search(
        r"^          ref: \$\{\{ steps.conformance.outputs.ref \}\}$", conformance, re.MULTILINE
    )
    assert re.search(r"^          path: conformance$", conformance, re.MULTILINE)
    readers = [
        step for step in steps if re.search(r"^        id: conformance$", step, re.MULTILINE)
    ]
    assert len(readers) == 1
    assert "< sdk/conformance-ref)" in readers[0]
    runners = [
        step
        for step in steps
        if re.search(r"^        run: just (mutation|test)$", step, re.MULTILINE)
    ]
    assert len(runners) == 1
    assert re.search(r"^        working-directory: sdk$", runners[0], re.MULTILINE)
    assert re.search(r"^          CONFORMANCE_DIR: ../conformance$", runners[0], re.MULTILINE)
    assert re.search(r"^          CONFORMANCE_CONTEXT: ../conformance$", runners[0], re.MULTILINE)


def test_mutation_copies_the_files_its_selected_tests_read() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    copied = [Path(path) for path in config["tool"]["mutmut"]["also_copy"]]
    required = [
        "conformance/runner.py",
        "conformance/golden_table.py",
        "examples/buy.py",
        "scripts/check_mutation.py",
        "scripts/generate.py",
        "openapi.json",
        "README.md",
        "justfile",
        "compose.yaml",
        "conformance-ref",
        ".release-please-manifest.json",
        ".github/workflows/ci.yml",
        ".github/workflows/nightly.yml",
        ".github/workflows/publish.yml",
    ]
    for relative in required:
        assert (ROOT / relative).is_file(), relative
        assert any(Path(relative).is_relative_to(path) for path in copied), relative
