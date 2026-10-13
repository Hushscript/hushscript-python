# pyright: reportPrivateUsage=false
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import attrs
import httpx
import pytest

import hushscript._client as client_module
from conftest import TOKEN
from helpers import (
    FakeClock,
    Script,
    account_body,
    error_body,
    failing_body,
    job_body,
    reply,
    transcript_body,
)
from hushscript import (
    AsyncHushscript,
    AuthenticationError,
    Balance,
    ConfigurationError,
    Hushscript,
    NetworkError,
    RateLimitError,
)
from hushscript._client import user_agent
from hushscript._errors import ApiError
from hushscript._models import Job
from hushscript._redact import Secret
from hushscript.generated.api.default import (
    get_account,
    get_job,
    get_transcript,
    list_saved_cards,
)
from hushscript.resources.account import Account
from hushscript.resources.agent import account_of, rotated_of, signup_of
from hushscript.resources.billing import (
    card_list,
    hold_page,
    ledger_page,
    pack_list,
    purchase_of,
    transaction_page,
)
from hushscript.resources.jobs import job_page
from hushscript.resources.transcripts import deleted_page, summary_page
from hushscript.transcript import Transcript

if TYPE_CHECKING:
    from collections.abc import Callable

    from hushscript._json import ExtraFields
    from hushscript.generated.client import AuthenticatedClient


def _patch(monkeypatch: pytest.MonkeyPatch, script: Script) -> None:
    monkeypatch.setattr(client_module, "_sync_inner", script.sync)
    monkeypatch.setattr(client_module, "_async_inner", script.asynchronous)


ACCOUNT = {
    "balance_seconds": 7260,
    "held_seconds": 30,
    "credits_expire_at": 1798859045,
    "card_on_file": False,
    "data_region": "eu",
    "limits": {
        "max_daily_seconds": 36000,
        "max_active_jobs": 50,
        "active_jobs": 0,
        "used_today_seconds": 0,
    },
    "purchases_remaining_in_window": 2,
}


def test_never_prints_token() -> None:
    hs = Hushscript(TOKEN)
    surface = repr(hs) + str(hs) + str(vars(hs)) + repr(hs.api)
    assert TOKEN[12:] not in surface


def test_async_client_never_prints_token() -> None:
    hs = AsyncHushscript(TOKEN)
    assert TOKEN[12:] not in repr(hs) + str(vars(hs)) + repr(hs.api)


@pytest.mark.parametrize("client_type", [Hushscript, AsyncHushscript])
def test_the_api_client_never_holds_the_token(
    client_type: type[Hushscript | AsyncHushscript],
) -> None:
    hs = client_type(TOKEN)
    assert hs.api.token == ""
    assert TOKEN[12:] not in repr(attrs.asdict(hs.api, recurse=False))
    assert TOKEN[12:] not in repr(vars(hs.api))
    assert not any("authorization" in key.lower() for key in hs.api._headers)


def test_the_token_is_not_stored_on_the_httpx_client() -> None:
    hs = Hushscript(TOKEN)
    assert "authorization" not in hs.api.get_httpx_client().headers
    assert hs.api.get_httpx_client().headers["User-Agent"] == user_agent()


def test_the_api_client_runs_on_the_same_retrying_httpx_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(503), reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    clock = FakeClock()
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=clock)
    response = hs.api.get_httpx_client().get("/v1/account")
    assert response.status_code == 200
    assert script.calls == 2
    assert script.requests[0].headers["Authorization"] == f"Bearer {TOKEN}"


def test_the_generated_operation_functions_use_the_hardened_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(503), reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=FakeClock())
    result = get_account.sync_detailed(client=hs.api)
    assert result.status_code == 200
    assert script.calls == 2


def test_user_agent_names_the_sdk_and_the_runtime() -> None:
    assert user_agent().startswith("hushscript-python/")
    assert " python/3." in user_agent()


def test_balance_reads_the_account(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, Script([reply(200, ACCOUNT)]))
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010")
    balance = hs.balance()
    assert isinstance(balance, Balance)
    assert (balance.seconds, balance.minutes, balance.held_seconds) == (7260, 121, 30)
    assert balance.expires_at is not None
    assert balance.expires_at.year == 2027
    assert balance.purchases_remaining == 2


def test_balance_with_debt_truncates_toward_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"balance_seconds": -90, "held_seconds": 0, "credits_expire_at": None}
    _patch(monkeypatch, Script([reply(200, body)]))
    balance = Hushscript(TOKEN, base_url="http://127.0.0.1:4010").balance()
    assert (balance.minutes, balance.expires_at, balance.purchases_remaining) == (-1, None, None)


@pytest.mark.parametrize(
    "body", [[], {"balance_seconds": "x", "held_seconds": 0}, {"balance_seconds": 1}]
)
def test_balance_rejects_an_unexpected_shape(monkeypatch: pytest.MonkeyPatch, body: object) -> None:
    _patch(monkeypatch, Script([reply(200, body)]))
    with pytest.raises(ApiError, match="account response"):
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010").balance()


def test_a_401_that_echoes_the_token_raises_a_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    body = error_body("unauthorized", 2000, details=f"bad token {TOKEN}")
    _patch(monkeypatch, Script([reply(401, body)]))
    with pytest.raises(AuthenticationError) as raised:
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010").balance()
    error = raised.value
    assert TOKEN[12:] not in " ".join(
        [str(error), repr(error), error.hint or "", repr(error.details)]
    )


def test_retry_after_61_raises_at_once_without_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch, Script([reply(429, error_body("rate_limited", 5000), {"Retry-After": "61"})])
    )
    clock = FakeClock()
    with pytest.raises(RateLimitError) as raised:
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=clock).balance()
    assert raised.value.retry_after == 61
    assert clock.sleeps == []


def test_a_retry_after_of_400_digits_raises_at_once_without_sleeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply_429 = reply(429, error_body("rate_limited", 5000), {"Retry-After": "9" * 400})
    script = Script([reply_429])
    _patch(monkeypatch, script)
    clock = FakeClock()
    with pytest.raises(RateLimitError) as raised:
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=clock).balance()
    assert raised.value.retry_after == float(2**53 - 1)
    assert clock.sleeps == []
    assert len(script.requests) == 1


def test_context_manager_closes_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, Script([reply(200, ACCOUNT)]))
    with Hushscript(TOKEN, base_url="http://127.0.0.1:4010") as hs:
        hs.balance()
    with pytest.raises(RuntimeError, match="closed"):
        hs.balance()


def test_a_dead_network_surfaces_as_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, Script([httpx.ConnectError("refused")]))
    with pytest.raises(NetworkError):
        Hushscript(
            TOKEN, base_url="http://127.0.0.1:4010", max_retries=1, clock=FakeClock()
        ).balance()


def test_environment_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUSHSCRIPT_TOKEN", TOKEN)
    monkeypatch.setenv("HUSHSCRIPT_BASE_URL", "http://127.0.0.1:4010")
    _patch(monkeypatch, Script([reply(200, ACCOUNT)]))
    assert Hushscript().balance().seconds == 7260


@pytest.mark.anyio
async def test_async_balance_and_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, Script([reply(503), reply(200, ACCOUNT)]))
    async with AsyncHushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=FakeClock()) as hs:
        assert (await hs.balance()).minutes == 121
    _patch(monkeypatch, Script([reply(401, error_body("unauthorized", 2000))]))
    async with AsyncHushscript(TOKEN, base_url="http://127.0.0.1:4010") as hs:
        with pytest.raises(AuthenticationError):
            await hs.balance()


def test_a_rotated_token_reaches_the_next_request_through_the_api_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010")
    new_token = TOKEN.replace("pat.0", "pat.1", 1)
    hs._config.credentials.replace(new_token)
    get_account.sync_detailed(client=hs.api)
    assert script.requests[0].headers["Authorization"] == f"Bearer {new_token}"
    assert hs.api.token == ""


@pytest.mark.parametrize(
    ("method", "argument"),
    [
        ("with_timeout", httpx.Timeout(300)),
        ("with_headers", {"X-Test": "1"}),
        ("with_cookies", {"a": "b"}),
    ],
)
def test_derived_api_clients_keep_the_hardened_transport(
    monkeypatch: pytest.MonkeyPatch, method: str, argument: object
) -> None:
    script = Script([reply(503), reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=FakeClock())
    before = hs._http.timeout
    derived: AuthenticatedClient = getattr(hs.api, method)(argument)
    assert derived is not hs.api
    assert derived.token == ""
    assert get_account.sync_detailed(client=derived).status_code == 200
    assert script.calls == 2
    assert script.requests[1].headers["Authorization"] == f"Bearer {TOKEN}"
    assert hs._http.timeout == before
    assert TOKEN[12:] not in repr(derived)


def test_a_derived_client_carries_its_change_and_leaves_the_original_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010")
    derived = hs.api.with_headers({"X-Test": "1"}).with_timeout(httpx.Timeout(7))
    get_account.sync_detailed(client=derived)
    assert script.requests[0].headers["X-Test"] == "1"
    assert script.requests[0].headers["User-Agent"] == user_agent()
    assert derived.get_httpx_client().timeout == httpx.Timeout(7)
    assert "x-test" not in hs.api.get_httpx_client().headers


def test_closing_a_derived_client_leaves_the_shared_transport_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    hs = Hushscript(TOKEN, base_url="http://127.0.0.1:4010")
    with hs.api.with_timeout(httpx.Timeout(7)) as derived:
        get_account.sync_detailed(client=derived)
    assert hs.balance().seconds == 7260


def test_the_sync_api_client_refuses_to_build_an_unhardened_async_client() -> None:
    hs = Hushscript(TOKEN)
    with pytest.raises(ConfigurationError, match="sync client"):
        hs.api.get_async_httpx_client()


@pytest.mark.anyio
async def test_the_async_api_client_refuses_to_build_an_unhardened_sync_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([reply(503), reply(200, ACCOUNT)])
    _patch(monkeypatch, script)
    async with AsyncHushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=FakeClock()) as hs:
        with pytest.raises(ConfigurationError, match="async client"):
            hs.api.get_httpx_client()
        derived = hs.api.with_timeout(httpx.Timeout(300))
        assert (await get_account.asyncio_detailed(client=derived)).status_code == 200
        assert script.calls == 2
        assert hs._http.timeout == httpx.Timeout(60.0)


def test_an_explicit_log_level_beats_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUSHSCRIPT_LOG", "debug")
    assert Hushscript(TOKEN, log_level="off")._config.log_level == "off"
    assert Hushscript(TOKEN)._config.log_level == "debug"
    assert AsyncHushscript(TOKEN, log_level="off")._config.log_level == "off"
    assert AsyncHushscript(TOKEN)._config.log_level == "debug"


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_a_retry_after_above_60_raises_the_status_class_with_retry_after(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    script = Script([reply(status, error_body("server_error", 9000), {"Retry-After": "61"})])
    _patch(monkeypatch, script)
    clock = FakeClock()
    with pytest.raises(ApiError) as raised:
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=clock).balance()
    assert (raised.value.status, raised.value.retry_after) == (status, 61)
    assert clock.sleeps == []
    assert script.calls == 1


def test_a_body_that_fails_after_the_headers_is_a_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = Script([failing_body(httpx.ReadTimeout("slow"))])
    _patch(monkeypatch, script)
    with pytest.raises(NetworkError):
        Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=FakeClock()).balance()
    assert script.calls == 4


UNKNOWN_FIELD = {"x_future": {"nested": [1, None, {"new": True}]}}


def test_hs_api_keeps_unknown_fields_of_nested_response_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both generated and friendly models preserve unknown nested fields."""
    account = account_body()
    account["limits"] = {**account["limits"], **UNKNOWN_FIELD}  # type: ignore[dict-item]
    card = {
        "id": "pm_1",
        "type": "card",
        "brand": "visa",
        "last4": "4242",
        "exp_month": 12,
        "exp_year": 2030,
        "email": None,
        "is_default": True,
        "fast_checkout_eligible": True,
        **UNKNOWN_FIELD,
    }
    job = job_body("job_1", "done")
    job["options"] = {**job["options"], **UNKNOWN_FIELD}  # type: ignore[dict-item]
    transcript = transcript_body()
    utterance = {"speaker": "A", "start_ms": 0, "end_ms": 1000, "text": "Hi.", **UNKNOWN_FIELD}
    transcript["body"] = {
        "version": 1,
        "original": {"utterances": [utterance]},
        "translations": {},
    }
    script = Script(
        [
            reply(200, account),
            reply(200, {"default_id": "pm_1", "methods": [card]}),
            reply(200, job),
            reply(200, transcript),
            reply(200, account),
            reply(200, {"default_id": "pm_1", "methods": [card]}),
            reply(200, job),
            reply(200, transcript),
        ]
    )
    _patch(monkeypatch, script)
    with Hushscript(TOKEN, base_url="http://127.0.0.1:4010", clock=FakeClock()) as hs:
        limits = cast("Any", get_account.sync(client=hs.api)).limits
        methods = cast("Any", list_saved_cards.sync(client=hs.api)).methods
        options = cast("Any", get_job.sync("job_1", client=hs.api)).options
        found = cast("Any", get_transcript.sync("tr_1", client=hs.api))
        assert hs.account().limits.extra == UNKNOWN_FIELD
        assert hs.billing.cards().cards[0].extra == UNKNOWN_FIELD
        assert hs.jobs.get("job_1").options.extra == UNKNOWN_FIELD
        assert hs.transcripts.get("tr_1").utterances[0].extra == UNKNOWN_FIELD
    assert limits.additional_properties == UNKNOWN_FIELD
    assert methods[0].additional_properties == UNKNOWN_FIELD
    assert options.additional_properties == UNKNOWN_FIELD
    assert found.body.original.utterances[0].additional_properties == UNKNOWN_FIELD


_EXTRA_CASES: list[tuple[Callable[[object], ExtraFields], dict[str, object]]] = [
    (Account.from_body, account_body()),
    (Balance.from_account, {"balance_seconds": 60, "held_seconds": 0}),
    (Job.from_body, job_body("job_1", "done")),
    (Transcript.from_api, transcript_body()),
    (purchase_of, {"status": "ok", "balance_seconds": 60}),
    (
        signup_of,
        {
            "signup_id": "sg_1",
            "claim_secret": "cs_secret",
            "checkout_url": "https://checkout.test/pay",
            "amount": 599,
            "currency": "USD",
            "expires_at": 1700001800,
        },
    ),
    (
        lambda body: account_of(Secret(TOKEN), cast("dict[str, object]", body)),
        {"user_id": "u_1", "scopes": [], "balance_seconds": 60},
    ),
    (
        lambda body: rotated_of(Secret(TOKEN), cast("dict[str, object]", body)),
        {"pat_id": "p_1", "scopes": [], "expires_at": None},
    ),
    (card_list, {"default_id": None, "methods": []}),
    (job_page, {"jobs": [], "next_cursor": None}),
    (summary_page, {"transcripts": [], "next_cursor": None}),
    (deleted_page, {"deleted": [], "next_cursor": None}),
    (transaction_page, {"transactions": [], "next_cursor": None}),
    (ledger_page, {"entries": [], "next_cursor": None}),
    (hold_page, {"holds": [], "next_cursor": None}),
]

# API fields that have no friendly attribute also stay in `extra`.
_UNMODELED: dict[Callable[[object], ExtraFields], dict[str, object]] = {
    Job.from_body: {"private_result_expires_at": None, "private_result_available": False},
    Transcript.from_api: {"matter_code": None, "client_code": None},
}


@pytest.mark.parametrize(("parse", "body"), _EXTRA_CASES)
def test_friendly_results_keep_unknown_fields_in_an_independent_read_only_mapping(
    parse: Callable[[object], ExtraFields], body: dict[str, object]
) -> None:
    fields = {**body, "x_future": {"nested": [1, None, {"new": True}]}}
    result = parse(fields)
    assert result.extra == {**_UNMODELED.get(parse, {}), **UNKNOWN_FIELD}
    with pytest.raises(TypeError):
        cast("dict[str, object]", result.extra)["other"] = True
    cast("dict[str, object]", fields["x_future"])["nested"] = []
    cast("dict[str, object]", result.extra["x_future"])["nested"] = []
    assert result.extra == {**_UNMODELED.get(parse, {}), **UNKNOWN_FIELD}


_ROW_CASES: list[tuple[Callable[[object], ExtraFields], str, dict[str, object]]] = [
    (
        lambda body: pack_list(body)[0],
        "packs",
        {
            "id": "45min",
            "seconds": 2700,
            "amount": 199,
            "currency": "USD",
            "referral_bonus_seconds": 0,
        },
    ),
    (
        lambda body: card_list(body).cards[0],
        "methods",
        {
            "id": "pm_1",
            "type": "card",
            "brand": "visa",
            "last4": "4242",
            "exp_month": 12,
            "exp_year": 2030,
            "is_default": True,
            "fast_checkout_eligible": True,
        },
    ),
    (
        lambda body: transaction_page(body).items[0],
        "transactions",
        {
            "id": 1,
            "seconds": 60,
            "amount_cents": 199,
            "amount_refunded_cents": 0,
            "currency": "USD",
            "status": "completed",
            "created_at": 1700000000,
        },
    ),
    (
        lambda body: ledger_page(body).items[0],
        "entries",
        {"id": 1, "delta_seconds": 60, "kind": "purchase", "created_at": 1700000000},
    ),
    (
        lambda body: hold_page(body).items[0],
        "holds",
        {"id": "h_1", "kind": "transcription", "seconds": 60, "created_at": 1700000000},
    ),
    (
        lambda body: summary_page(body).items[0],
        "transcripts",
        {
            "id": "tr_1",
            "title": "Call",
            "language_detected": None,
            "duration_seconds": 60,
            "created_at": 1700000000,
            "auto_delete_at": None,
            "tags": [],
        },
    ),
    (
        lambda body: deleted_page(body).items[0],
        "deleted",
        {
            "id": "tr_1",
            "title": "Call",
            "duration_seconds": 60,
            "created_at": 1700000000,
            "deleted_at": 1700000060,
            "cause": "manual",
            "receipt": {"x_nested": True},
        },
    ),
]


@pytest.mark.parametrize(("parse", "key", "item"), _ROW_CASES)
def test_friendly_billing_and_transcript_rows_preserve_nested_unknown_fields(
    parse: Callable[[object], ExtraFields], key: str, item: dict[str, object]
) -> None:
    result = parse({key: [{**item, **UNKNOWN_FIELD}], "next_cursor": None, "default_id": None})
    assert result.extra == UNKNOWN_FIELD
