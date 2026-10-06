from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Self

import httpx

from ._clock import Clock, SystemClock
from ._config import Config, resolve_config
from ._errors import ConfigurationError, raise_for_response
from ._http import AsyncRetryingTransport, RetryingTransport, TransportSettings
from ._log import RequestLog
from ._models import Balance
from ._redact import REDACTED
from ._version import __version__
from .generated.client import AuthenticatedClient

if TYPE_CHECKING:
    from types import TracebackType


def user_agent() -> str:
    return f"hushscript-python/{__version__} python/{platform.python_version()}"


class _SharedTransport(httpx.BaseTransport):
    """Gives a derived httpx client the hardened transport without letting it close it."""

    def __init__(self, inner: httpx.BaseTransport) -> None:
        self._inner = inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self._inner.handle_request(request)

    def close(self) -> None:
        """The owning `Hushscript` closes the transport."""


class _SharedAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        """The owning `AsyncHushscript` closes the transport."""


class _ApiClient(AuthenticatedClient):
    """The generated client on the hardened httpx client.

    It holds no token: the transport adds the Authorization header per request, so a rotated token
    is picked up and nothing here can show it. The generated `with_*` methods would build a plain
    httpx client without the retrying transport, so they are replaced by ones that keep it.
    """

    _sync_transport: httpx.BaseTransport | None = None
    _async_transport: httpx.AsyncBaseTransport | None = None

    def __repr__(self) -> str:
        return f"AuthenticatedClient(base_url={self._base_url!r}, token={REDACTED!r})"

    def bind_sync(self, client: httpx.Client, transport: httpx.BaseTransport) -> None:
        self.set_httpx_client(client)
        self._sync_transport = transport

    def bind_async(self, client: httpx.AsyncClient, transport: httpx.AsyncBaseTransport) -> None:
        self.set_async_httpx_client(client)
        self._async_transport = transport

    def get_httpx_client(self) -> httpx.Client:
        if self._client is None:
            raise ConfigurationError("This is an async client; use get_async_httpx_client().")
        return self._client

    def get_async_httpx_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            raise ConfigurationError("This is a sync client; use get_httpx_client().")
        return self._async_client

    def with_timeout(self, timeout: httpx.Timeout) -> _ApiClient:
        return self._derive(timeout=timeout)

    def with_headers(self, headers: dict[str, str]) -> _ApiClient:
        return self._derive(headers=headers)

    def with_cookies(self, cookies: dict[str, str]) -> _ApiClient:
        return self._derive(cookies=cookies)

    def _derive(
        self,
        *,
        timeout: httpx.Timeout | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> _ApiClient:
        derived = _ApiClient(base_url=self._base_url, token="", timeout=timeout or self._timeout)
        if self._client is not None and self._sync_transport is not None:
            derived.bind_sync(
                httpx.Client(
                    base_url=self._client.base_url,
                    headers=_merged_headers(self._client.headers, headers),
                    cookies=_merged_cookies(self._client.cookies, cookies),
                    timeout=timeout or self._client.timeout,
                    transport=_SharedTransport(self._sync_transport),
                ),
                self._sync_transport,
            )
        if self._async_client is not None and self._async_transport is not None:
            derived.bind_async(
                httpx.AsyncClient(
                    base_url=self._async_client.base_url,
                    headers=_merged_headers(self._async_client.headers, headers),
                    cookies=_merged_cookies(self._async_client.cookies, cookies),
                    timeout=timeout or self._async_client.timeout,
                    transport=_SharedAsyncTransport(self._async_transport),
                ),
                self._async_transport,
            )
        return derived


def _merged_headers(current: httpx.Headers, extra: dict[str, str] | None) -> httpx.Headers:
    merged = httpx.Headers(current)
    merged.update(extra or {})
    return merged


def _merged_cookies(current: httpx.Cookies, extra: dict[str, str] | None) -> httpx.Cookies:
    merged = httpx.Cookies(current)
    merged.update(extra or {})
    return merged


def _sync_inner() -> httpx.BaseTransport:
    return httpx.HTTPTransport()


def _async_inner() -> httpx.AsyncBaseTransport:
    return httpx.AsyncHTTPTransport()


def _api_client(config: Config) -> _ApiClient:
    return _ApiClient(base_url=config.base_url, token="", timeout=httpx.Timeout(config.timeout))


def _settings(config: Config, clock: Clock) -> TransportSettings:
    return TransportSettings(
        clock=clock,
        log=RequestLog(config.log_level),
        credentials=config.credentials,
        max_retries=config.max_retries,
        base_url=httpx.URL(config.base_url),
        timeout=config.timeout,
    )


class Hushscript:
    """The synchronous Hushscript client. `api` is the generated low-level client on the same
    retrying transport."""

    api: AuthenticatedClient

    def __init__(  # the public surface of spec section 3
        self,
        token: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 60,
        max_retries: int = 3,
        log_level: str | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._config = resolve_config(
            token, base_url=base_url, timeout=timeout, max_retries=max_retries, log_level=log_level
        )
        self._clock: Clock = clock or SystemClock()
        transport = RetryingTransport(_sync_inner(), _settings(self._config, self._clock))
        self._http = httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers={"User-Agent": user_agent()},
            transport=transport,
        )
        api = _api_client(self._config)
        api.bind_sync(self._http, transport)
        self.api = api

    def balance(self) -> Balance:
        response = self._http.get("/v1/account")
        raise_for_response(response, credentials=self._config.credentials)
        return Balance.from_account(response.json())

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"Hushscript(base_url={self._config.base_url!r})"


class AsyncHushscript:
    """The asyncio client with the same surface as `Hushscript`."""

    api: AuthenticatedClient

    def __init__(  # the public surface of spec section 3
        self,
        token: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 60,
        max_retries: int = 3,
        log_level: str | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._config = resolve_config(
            token, base_url=base_url, timeout=timeout, max_retries=max_retries, log_level=log_level
        )
        self._clock: Clock = clock or SystemClock()
        transport = AsyncRetryingTransport(_async_inner(), _settings(self._config, self._clock))
        self._http = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers={"User-Agent": user_agent()},
            transport=transport,
        )
        api = _api_client(self._config)
        api.bind_async(self._http, transport)
        self.api = api

    async def balance(self) -> Balance:
        response = await self._http.get("/v1/account")
        raise_for_response(response, credentials=self._config.credentials)
        return Balance.from_account(response.json())

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return f"AsyncHushscript(base_url={self._config.base_url!r})"
