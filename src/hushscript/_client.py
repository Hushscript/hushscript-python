from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Self

import httpx

from ._clock import Clock, SystemClock
from ._config import Config, resolve_config
from ._errors import raise_for_response
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


class _ApiClient(AuthenticatedClient):
    """The generated client, with a repr that never shows the token."""

    def __repr__(self) -> str:
        return f"AuthenticatedClient(base_url={self._base_url!r}, token={REDACTED!r})"


def _sync_inner() -> httpx.BaseTransport:
    return httpx.HTTPTransport()


def _async_inner() -> httpx.AsyncBaseTransport:
    return httpx.AsyncHTTPTransport()


def _api_client(config: Config) -> _ApiClient:
    return _ApiClient(
        base_url=config.base_url,
        token=config.credentials.token or "",
        timeout=httpx.Timeout(config.timeout),
    )


def _settings(config: Config, clock: Clock) -> TransportSettings:
    return TransportSettings(
        clock=clock,
        log=RequestLog(config.log_level),
        credentials=config.credentials,
        max_retries=config.max_retries,
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
        log_level: str = "off",
        clock: Clock | None = None,
    ) -> None:
        self._config = resolve_config(
            token, base_url=base_url, timeout=timeout, max_retries=max_retries, log_level=log_level
        )
        self._clock: Clock = clock or SystemClock()
        self._http = httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers={"User-Agent": user_agent()},
            transport=RetryingTransport(_sync_inner(), _settings(self._config, self._clock)),
        )
        api = _api_client(self._config)
        api.set_httpx_client(self._http)
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
        log_level: str = "off",
        clock: Clock | None = None,
    ) -> None:
        self._config = resolve_config(
            token, base_url=base_url, timeout=timeout, max_retries=max_retries, log_level=log_level
        )
        self._clock: Clock = clock or SystemClock()
        self._http = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers={"User-Agent": user_agent()},
            transport=AsyncRetryingTransport(_async_inner(), _settings(self._config, self._clock)),
        )
        api = _api_client(self._config)
        api.set_async_httpx_client(self._http)
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
