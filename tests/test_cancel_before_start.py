from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import httpx
import pytest

import hushscript._client as client_module
from conftest import TOKEN
from helpers import cancellation_notes, snapshot
from hushscript import AgentInfo, AsyncHushscript

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("operation", "path", "hint"),
    [
        (
            "agent_claim",
            "/v1/agent/accounts/signup/claim",
            (
                "The claim may have succeeded. Retrying will fail with agent_claim_invalid. "
                "If you have no token, contact support with the signup id."
            ),
        ),
        (
            "agent.rotate_token",
            "/v1/agent/credentials/rotate",
            (
                "The old token may already be revoked. Try a request with it; if it fails, "
                "the new token was lost and the account needs support."
            ),
        ),
        ("agent_signup", "/v1/agent/accounts", None),
    ],
)
async def test_canceling_a_public_call_after_sending_reports_the_unknown_outcome(
    operation: str,
    path: str,
    hint: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waiting = asyncio.Event()
    requests: list[httpx.Request] = []

    async def hold(request: httpx.Request) -> httpx.Response:
        requests.append(snapshot(request))
        async for _ in cast("httpx.AsyncByteStream", request.stream):
            pass
        waiting.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr(client_module, "_async_inner", lambda: httpx.MockTransport(hold))
    async with AsyncHushscript(TOKEN) as hs:
        calls: dict[str, Callable[[], Awaitable[object]]] = {
            "agent_signup": lambda: AsyncHushscript.agent_signup(
                email="agent@example.com",
                pack="45min",
                accept_terms="version",
                agent=AgentInfo(name="test", platform="test"),
            ),
            "agent_claim": lambda: AsyncHushscript.agent_claim("signup", "claim-secret"),
            "agent.rotate_token": hs.agent.rotate_token,
        }
        task = asyncio.ensure_future(calls[operation]())
        try:
            await asyncio.wait_for(waiting.wait(), timeout=5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError) as raised:
                await task
            assert task.cancelled()
            notes = cancellation_notes(raised.value)
            assert any("outcome is unknown" in note for note in notes)
            if hint is not None:
                assert any(hint in note for note in notes)
            assert len(requests) == 1
            assert requests[0].method == "POST"
            assert requests[0].url.path == path
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
