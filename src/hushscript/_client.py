from __future__ import annotations

import platform
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, BinaryIO, Self

import httpx

from ._clock import Clock, SystemClock
from ._config import PART_TIMEOUT, Config, resolve_config, resolve_tokenless_config
from ._errors import ConfigurationError
from ._http import AsyncRetryingTransport, RetryingTransport, TransportSettings
from ._log import RequestLog
from ._pacing import TokenBucket
from ._redact import REDACTED
from ._response import parsed
from ._version import __version__
from .generated.client import AuthenticatedClient
from .resources.account import Account, Balance
from .resources.agent import (
    Agent,
    AgentAccount,
    AgentInfo,
    AgentSignup,
    AsyncAgent,
    check_accept_terms,
    claim_body,
    claim_path,
    claimed,
    signed_up,
    signup_body,
)
from .resources.billing import AsyncBilling, Billing, Purchase
from .resources.jobs import AsyncJobs, Jobs
from .resources.transcripts import AsyncTranscripts, Transcripts
from .transcribe import apipeline, pipeline
from .transcribe.pipeline import Callbacks
from .transcribe.preflight import Options
from .transcribe.session import AsyncSession, SyncSession
from .transcribe.wait import DEFAULT_WAIT_TIMEOUT

if TYPE_CHECKING:
    import os
    from collections.abc import AsyncGenerator, Callable, Generator, Sequence
    from types import TracebackType

    from ._models import Progress
    from .transcript import Transcript


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


def _settings(config: Config, clock: Clock, bucket: TokenBucket) -> TransportSettings:
    return TransportSettings(
        clock=clock,
        log=RequestLog(config.log_level),
        credentials=config.credentials,
        max_retries=config.max_retries,
        base_url=httpx.URL(config.base_url),
        timeout=config.timeout,
        bucket=bucket,
    )


# Signed direct-to-R2 part URLs are not API requests: this base URL matches no request, so the
# client built on it never sends the token and the part class of the call is honored.
_R2_ORIGIN = httpx.URL("https://r2.invalid")


def _r2_settings(config: Config, clock: Clock) -> TransportSettings:
    return TransportSettings(
        clock=clock,
        log=RequestLog(config.log_level),
        credentials=None,
        max_retries=config.max_retries,
        base_url=_R2_ORIGIN,
        timeout=PART_TIMEOUT,
    )


@contextmanager
def _tokenless_http(config: Config, clock: Clock | None) -> Generator[httpx.Client]:
    """A client for the calls that need no token: it sends none, and never retries."""
    chosen = clock or SystemClock()
    settings = _settings(config, chosen, TokenBucket(chosen))
    with httpx.Client(
        base_url=config.base_url,
        timeout=config.timeout,
        headers={"User-Agent": user_agent()},
        transport=RetryingTransport(_sync_inner(), settings),
        follow_redirects=False,
    ) as http:
        yield http


@asynccontextmanager
async def _tokenless_async_http(
    config: Config, clock: Clock | None
) -> AsyncGenerator[httpx.AsyncClient]:
    chosen = clock or SystemClock()
    settings = _settings(config, chosen, TokenBucket(chosen))
    async with httpx.AsyncClient(
        base_url=config.base_url,
        timeout=config.timeout,
        headers={"User-Agent": user_agent()},
        transport=AsyncRetryingTransport(_async_inner(), settings),
        follow_redirects=False,
    ) as http:
        yield http


def _options(  # noqa: PLR0913  the keyword surface of `transcribe()`, validated before any request
    *,
    title: str | None,
    language: str | None,
    speakers: bool,
    translate_to: Sequence[str] | None,
    keyterms: Sequence[str] | None,
    prompt: str | None,
    medical: bool,
    multichannel: bool,
    auto_insights: bool | None,
    matter_code: str | None,
    duration_seconds: float | None,
    idempotency_key: str | None,
    concurrency: int,
    wait_timeout: float,
) -> Options:
    return Options(
        title=title,
        language=language,
        speakers=speakers,
        translate_to=tuple(translate_to or ()),
        keyterms=tuple(keyterms or ()),
        prompt=prompt,
        medical=medical,
        multichannel=multichannel,
        auto_insights=auto_insights,
        matter_code=matter_code,
        duration_seconds=duration_seconds,
        idempotency_key=idempotency_key,
        concurrency=concurrency,
        wait_timeout=wait_timeout,
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
        bucket = TokenBucket(self._clock)
        transport = RetryingTransport(_sync_inner(), _settings(self._config, self._clock, bucket))
        self._http = httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers={"User-Agent": user_agent()},
            transport=transport,
            follow_redirects=False,
        )
        self._r2 = httpx.Client(
            timeout=PART_TIMEOUT,
            headers={"User-Agent": user_agent()},
            transport=RetryingTransport(_sync_inner(), _r2_settings(self._config, self._clock)),
            follow_redirects=False,
        )
        api = _api_client(self._config)
        api.bind_sync(self._http, transport)
        self.api = api
        self._session = SyncSession(
            clock=self._clock,
            credentials=self._config.credentials,
            log=RequestLog(self._config.log_level),
            http=self._http,
            r2=self._r2,
        )
        self.jobs = Jobs(self._session)
        self.transcripts = Transcripts(self._session)
        self.billing = Billing(self._session)
        self.agent = Agent(self._session)

    def balance(self) -> Balance:
        """What the account can spend. Net of holds: `held_seconds` says how much of it is already
        committed, and is not to be subtracted again."""
        response = self._http.get("/v1/account")
        return parsed(response, self._config.credentials, Balance.from_account)

    def account(self) -> Account:
        """The account: balance, limits, card on file and data region."""
        response = self._http.get("/v1/account")
        return parsed(response, self._config.credentials, Account.from_body)

    def buy(
        self,
        pack: str,
        *,
        acknowledge_no_refund: bool = False,
        idempotency_key: str | None = None,
    ) -> Purchase:
        """Buys a minute pack with the saved card; it is `hs.billing.buy`."""
        return self.billing.buy(
            pack, acknowledge_no_refund=acknowledge_no_refund, idempotency_key=idempotency_key
        )

    @staticmethod
    def agent_signup(  # noqa: PLR0913  the keyword surface of spec 6.6
        *,
        email: str,
        pack: str,
        accept_terms: str,
        agent: AgentInfo,
        data_region: str | None = None,
        dry_run: bool = False,
        base_url: str | None = None,
        timeout: float = 60,
        log_level: str | None = None,
        clock: Clock | None = None,
    ) -> AgentSignup:
        """Opens an agent account. It needs no token (HUSHSCRIPT_TOKEN is not read or sent): the
        agent then has the checkout paid at `checkout_url` and claims the account with
        `agent_claim`. `accept_terms`, the policy version being accepted, is never defaulted. The
        request is never retried; a lost answer is an `OutcomeUnknownError`."""
        check_accept_terms(accept_terms)
        config = resolve_tokenless_config(base_url=base_url, timeout=timeout, log_level=log_level)
        body = signup_body(
            email=email,
            pack=pack,
            accept_terms=accept_terms,
            agent=agent,
            data_region=data_region,
            dry_run=dry_run,
        )
        with _tokenless_http(config, clock) as http:
            return signed_up(http.post("/v1/agent/accounts", json=body), config.credentials)

    @staticmethod
    def agent_claim(
        signup_id: str,
        claim_secret: str,
        *,
        base_url: str | None = None,
        timeout: float = 60,
        log_level: str | None = None,
        clock: Clock | None = None,
    ) -> AgentAccount:
        """Claims a paid agent signup and returns the account's token, which the server shows
        once: write it down before doing anything else. It answers `wrong_state` (a
        `ConflictError`) until the checkout is paid, and is never retried: a lost answer, or one
        without a usable token, is an `OutcomeUnknownError` whose hint says what to check."""
        path = claim_path(signup_id)
        config = resolve_tokenless_config(base_url=base_url, timeout=timeout, log_level=log_level)
        with _tokenless_http(config, clock) as http:
            response = http.post(path, json=claim_body(claim_secret))
            return claimed(response, config.credentials)

    def transcribe(  # noqa: PLR0913  the keyword surface of spec 6.1
        self,
        file: str | os.PathLike[str] | bytes | BinaryIO,
        *,
        title: str | None = None,
        language: str | None = None,
        speakers: bool = True,
        translate_to: Sequence[str] | None = None,
        keyterms: Sequence[str] | None = None,
        prompt: str | None = None,
        medical: bool = False,
        multichannel: bool = False,
        auto_insights: bool | None = None,
        matter_code: str | None = None,
        duration_seconds: float | None = None,
        size: int | None = None,
        idempotency_key: str | None = None,
        concurrency: int = 4,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
        on_progress: Callable[[Progress], None] | None = None,
        on_resume_token: Callable[[str], None] | None = None,
    ) -> Transcript:
        """Uploads `file`, waits for the transcript and returns it (spec 8). A non-seekable
        stream needs `size` and `duration_seconds`."""
        options = _options(
            title=title,
            language=language,
            speakers=speakers,
            translate_to=translate_to,
            keyterms=keyterms,
            prompt=prompt,
            medical=medical,
            multichannel=multichannel,
            auto_insights=auto_insights,
            matter_code=matter_code,
            duration_seconds=duration_seconds,
            idempotency_key=idempotency_key,
            concurrency=concurrency,
            wait_timeout=wait_timeout,
        )
        callbacks = Callbacks(on_progress=on_progress, on_resume_token=on_resume_token)
        return pipeline.run_transcribe(self._session, file, options, size, callbacks)

    def resume(
        self,
        token: str,
        file: str | os.PathLike[str] | bytes | BinaryIO | None = None,
        *,
        concurrency: int = 4,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
        on_progress: Callable[[Progress], None] | None = None,
    ) -> Transcript:
        """Picks a transcription up from the token of an earlier call (spec 7.3). `file` is needed
        only while the job is still uploading."""
        options = Options(concurrency=concurrency, wait_timeout=wait_timeout)
        return pipeline.run_resume(
            self._session, token, file, options, Callbacks(on_progress=on_progress)
        )

    def close(self) -> None:
        self._http.close()
        self._r2.close()

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
        bucket = TokenBucket(self._clock)
        transport = AsyncRetryingTransport(
            _async_inner(), _settings(self._config, self._clock, bucket)
        )
        self._http = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers={"User-Agent": user_agent()},
            transport=transport,
            follow_redirects=False,
        )
        self._r2 = httpx.AsyncClient(
            timeout=PART_TIMEOUT,
            headers={"User-Agent": user_agent()},
            transport=AsyncRetryingTransport(
                _async_inner(), _r2_settings(self._config, self._clock)
            ),
            follow_redirects=False,
        )
        api = _api_client(self._config)
        api.bind_async(self._http, transport)
        self.api = api
        self._session = AsyncSession(
            clock=self._clock,
            credentials=self._config.credentials,
            log=RequestLog(self._config.log_level),
            http=self._http,
            r2=self._r2,
        )
        self.jobs = AsyncJobs(self._session)
        self.transcripts = AsyncTranscripts(self._session)
        self.billing = AsyncBilling(self._session)
        self.agent = AsyncAgent(self._session)

    async def balance(self) -> Balance:
        response = await self._http.get("/v1/account")
        return parsed(response, self._config.credentials, Balance.from_account)

    async def account(self) -> Account:
        response = await self._http.get("/v1/account")
        return parsed(response, self._config.credentials, Account.from_body)

    async def buy(
        self,
        pack: str,
        *,
        acknowledge_no_refund: bool = False,
        idempotency_key: str | None = None,
    ) -> Purchase:
        return await self.billing.buy(
            pack, acknowledge_no_refund=acknowledge_no_refund, idempotency_key=idempotency_key
        )

    @staticmethod
    async def agent_signup(  # noqa: PLR0913  the keyword surface of spec 6.6
        *,
        email: str,
        pack: str,
        accept_terms: str,
        agent: AgentInfo,
        data_region: str | None = None,
        dry_run: bool = False,
        base_url: str | None = None,
        timeout: float = 60,  # noqa: ASYNC109  the same `timeout` as the constructor
        log_level: str | None = None,
        clock: Clock | None = None,
    ) -> AgentSignup:
        check_accept_terms(accept_terms)
        config = resolve_tokenless_config(base_url=base_url, timeout=timeout, log_level=log_level)
        body = signup_body(
            email=email,
            pack=pack,
            accept_terms=accept_terms,
            agent=agent,
            data_region=data_region,
            dry_run=dry_run,
        )
        async with _tokenless_async_http(config, clock) as http:
            response = await http.post("/v1/agent/accounts", json=body)
            return signed_up(response, config.credentials)

    @staticmethod
    async def agent_claim(
        signup_id: str,
        claim_secret: str,
        *,
        base_url: str | None = None,
        timeout: float = 60,  # noqa: ASYNC109  the same `timeout` as the constructor
        log_level: str | None = None,
        clock: Clock | None = None,
    ) -> AgentAccount:
        path = claim_path(signup_id)
        config = resolve_tokenless_config(base_url=base_url, timeout=timeout, log_level=log_level)
        async with _tokenless_async_http(config, clock) as http:
            response = await http.post(path, json=claim_body(claim_secret))
            return claimed(response, config.credentials)

    async def transcribe(  # noqa: PLR0913  the keyword surface of spec 6.1
        self,
        file: str | os.PathLike[str] | bytes | BinaryIO,
        *,
        title: str | None = None,
        language: str | None = None,
        speakers: bool = True,
        translate_to: Sequence[str] | None = None,
        keyterms: Sequence[str] | None = None,
        prompt: str | None = None,
        medical: bool = False,
        multichannel: bool = False,
        auto_insights: bool | None = None,
        matter_code: str | None = None,
        duration_seconds: float | None = None,
        size: int | None = None,
        idempotency_key: str | None = None,
        concurrency: int = 4,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
        on_progress: Callable[[Progress], None] | None = None,
        on_resume_token: Callable[[str], None] | None = None,
    ) -> Transcript:
        options = _options(
            title=title,
            language=language,
            speakers=speakers,
            translate_to=translate_to,
            keyterms=keyterms,
            prompt=prompt,
            medical=medical,
            multichannel=multichannel,
            auto_insights=auto_insights,
            matter_code=matter_code,
            duration_seconds=duration_seconds,
            idempotency_key=idempotency_key,
            concurrency=concurrency,
            wait_timeout=wait_timeout,
        )
        callbacks = Callbacks(on_progress=on_progress, on_resume_token=on_resume_token)
        return await apipeline.run_transcribe(self._session, file, options, size, callbacks)

    async def resume(
        self,
        token: str,
        file: str | os.PathLike[str] | bytes | BinaryIO | None = None,
        *,
        concurrency: int = 4,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
        on_progress: Callable[[Progress], None] | None = None,
    ) -> Transcript:
        options = Options(concurrency=concurrency, wait_timeout=wait_timeout)
        return await apipeline.run_resume(
            self._session, token, file, options, Callbacks(on_progress=on_progress)
        )

    async def aclose(self) -> None:
        await self._http.aclose()
        await self._r2.aclose()

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
