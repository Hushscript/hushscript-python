from __future__ import annotations

import asyncio
import os
from pathlib import Path

import golden_table
import httpx
import pytest
import runner

from hushscript import AsyncHushscript, Hushscript


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_format_uses_only_prepared_fixtures(tmp_path: Path, *, asynchronous: bool) -> None:
    directory = os.environ.get("CONFORMANCE_DIR")
    if not directory:
        pytest.fail("CONFORMANCE_DIR must point at a hushscript-sdk-conformance checkout")
    fixtures = Path(directory) / "fixtures"
    requested: list[str] = []

    def serve(request: httpx.Request) -> httpx.Response:
        name = request.url.path.removeprefix("/__files/fixtures/")
        requested.append(name)
        return httpx.Response(200, content=(fixtures / name).read_bytes())

    call: dict[str, object] = {"op": "format", "args": {}}
    with httpx.Client(base_url=runner.BASE_URL, transport=httpx.MockTransport(serve)) as control:
        files = runner.Files(control, tmp_path)
        files.prepare(call)

    expected = {
        name
        for golden in golden_table.all_goldens()
        for name in (f"transcripts/{golden.transcript}.json", f"exports/{golden.file}")
    }
    assert set(requested) == expected
    assert len(requested) == len(expected)

    async def invoke_async() -> runner.Json:
        async with AsyncHushscript(runner.TEST_TOKEN) as hs:
            return await runner._async_call(hs, call, files, None)  # pyright: ignore[reportPrivateUsage]

    if asynchronous:
        result = asyncio.run(invoke_async())
    else:
        with Hushscript(runner.TEST_TOKEN) as hs:
            result = runner._call(hs, call, files, None)  # pyright: ignore[reportPrivateUsage]

    assert result == {"checked": 72, "mismatches": []}
    assert len(requested) == len(expected)
    for name in expected:
        assert files.text(name).encode("utf-8") == (fixtures / name).read_bytes()


def test_fixture_text_preserves_bytes_and_fetches_once(tmp_path: Path) -> None:
    body = "\ufeffCafé\r\n  padded\n\rfinal\r\n".encode()
    requested: list[str] = []

    def serve(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(200, content=body)

    with httpx.Client(base_url=runner.BASE_URL, transport=httpx.MockTransport(serve)) as control:
        files = runner.Files(control, tmp_path)
        assert files.text("exports/exact.txt").encode("utf-8") == body
        assert files.text("exports/exact.txt").encode("utf-8") == body

    assert files.text("exports/exact.txt").encode("utf-8") == body
    assert requested == ["/__files/fixtures/exports/exact.txt"]
