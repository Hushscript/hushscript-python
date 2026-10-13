"""A client wired to a request handler, for tests that need to see the query of each request."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx

import hushscript._client as client_module
from conftest import TOKEN
from helpers import BASE_URL, FakeClock, snapshot
from hushscript import AsyncHushscript, Hushscript

if TYPE_CHECKING:
    import pytest

Handler = Callable[[httpx.Request], httpx.Response]


class Routes:
    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(snapshot(request))
        return self.handler(request)

    def sync(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def asynchronous(self) -> httpx.MockTransport:
        async def handler(request: httpx.Request) -> httpx.Response:
            return self._handle(request)

        return httpx.MockTransport(handler)

    def queries(self) -> list[dict[str, str]]:
        return [dict(request.url.params) for request in self.requests]


def hs_on(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> tuple[Hushscript, Routes]:
    routes = Routes(handler)
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    monkeypatch.setattr(client_module, "_async_inner", routes.asynchronous)
    return Hushscript(TOKEN, base_url=BASE_URL, clock=FakeClock()), routes


def async_hs_on(
    monkeypatch: pytest.MonkeyPatch, handler: Handler
) -> tuple[AsyncHushscript, Routes]:
    routes = Routes(handler)
    monkeypatch.setattr(client_module, "_sync_inner", routes.sync)
    monkeypatch.setattr(client_module, "_async_inner", routes.asynchronous)
    return AsyncHushscript(TOKEN, base_url=BASE_URL, clock=FakeClock()), routes
