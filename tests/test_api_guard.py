"""`hs.api` raises an SDK error for an answer the generated code cannot read, and a purchase made
through it carries its idempotency key on every error after it was sent (R61)."""

from __future__ import annotations

import json

import httpx
import pytest

from hushscript import ApiError, HushscriptError, NetworkError
from hushscript.generated.api.default import buy_minutes, get_account
from hushscript.generated.models.buy_minutes_body import BuyMinutesBody
from hushscript.generated.models.error import Error
from routes import Handler, async_hs_on, hs_on

KEY = "api-key-1"
BODY = BuyMinutesBody(pack="300min", idempotency_key=KEY, quick_payment_method_id="pm_1")
HTML = "<html><body>502 Bad Gateway</body></html>"


def html(status: int) -> httpx.Response:
    return httpx.Response(status, text=HTML, headers={"content-type": "text/html"})


def purchased(status: int, content: str) -> Handler:
    return lambda _request: httpx.Response(status, text=content)


def test_a_purchase_answered_with_html_502_twice_is_an_api_error_carrying_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = hs_on(monkeypatch, lambda _request: html(502))
    with pytest.raises(ApiError) as raised:
        buy_minutes.sync_detailed(client=hs.api, body=BODY)
    assert len(routes.requests) == 2
    assert raised.value.status == 502
    assert raised.value.idempotency_key == KEY
    assert not isinstance(raised.value.__cause__, json.JSONDecodeError)


def test_a_purchase_answered_200_with_a_body_that_is_not_json_is_bad_response_with_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, routes = hs_on(monkeypatch, purchased(200, HTML))
    with pytest.raises(ApiError) as raised:
        buy_minutes.sync_detailed(client=hs.api, body=BODY)
    assert len(routes.requests) == 1
    assert raised.value.code == "bad_response"
    assert raised.value.status == 200
    assert raised.value.idempotency_key == KEY


def test_a_purchase_answered_200_without_a_field_is_bad_response_with_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, purchased(200, json.dumps({"status": "ok"})))
    with pytest.raises(ApiError) as raised:
        buy_minutes.sync_detailed(client=hs.api, body=BODY)
    assert raised.value.code == "bad_response"
    assert raised.value.idempotency_key == KEY


def test_a_purchase_that_never_got_an_answer_carries_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    hs, _ = hs_on(monkeypatch, refuse)
    with pytest.raises(NetworkError) as raised:
        buy_minutes.sync_detailed(client=hs.api, body=BODY)
    assert raised.value.idempotency_key == KEY


def test_a_usable_purchase_answer_is_returned_as_the_generated_code_parses_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, purchased(200, json.dumps({"status": "ok", "balance_seconds": 600})))
    result = buy_minutes.sync_detailed(client=hs.api, body=BODY)
    assert result.status_code == 200
    assert getattr(result.parsed, "balance_seconds", None) == 600


def test_a_documented_error_answer_is_still_returned_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, purchased(422, json.dumps({"error": "bad_request", "code": 1})))
    result = buy_minutes.sync_detailed(client=hs.api, body=BODY)
    assert result.status_code == 422
    assert isinstance(result.parsed, Error)


def test_a_non_billing_operation_answered_200_with_a_body_that_is_not_json_is_bad_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, purchased(200, HTML))
    with pytest.raises(ApiError) as raised:
        get_account.sync_detailed(client=hs.api)
    assert raised.value.code == "bad_response"
    assert raised.value.idempotency_key is None


def test_a_non_billing_operation_answered_200_without_a_field_is_bad_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, purchased(200, json.dumps({"held_seconds": 0})))
    with pytest.raises(HushscriptError) as raised:
        get_account.sync(client=hs.api)
    assert raised.value.code == "bad_response"
    assert not isinstance(raised.value.__cause__, KeyError)


def test_a_non_billing_operation_answered_with_html_500_is_the_error_of_its_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, lambda _request: html(500))
    with pytest.raises(ApiError) as raised:
        get_account.sync_detailed(client=hs.api)
    assert raised.value.status == 500
    assert raised.value.idempotency_key is None


def test_a_call_that_is_not_a_generated_operation_still_gets_the_raw_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = hs_on(monkeypatch, purchased(200, HTML))
    assert hs.api.get_httpx_client().get("/v1/account").text == HTML


@pytest.mark.anyio
async def test_the_async_client_guards_a_purchase_the_same_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hs, _ = async_hs_on(monkeypatch, purchased(200, HTML))
    async with hs:
        with pytest.raises(ApiError) as raised:
            await buy_minutes.asyncio_detailed(client=hs.api, body=BODY)
        assert raised.value.code == "bad_response"
        assert raised.value.idempotency_key == KEY
        with pytest.raises(ApiError) as plain:
            await get_account.asyncio_detailed(client=hs.api)
        assert plain.value.code == "bad_response"
        assert plain.value.idempotency_key is None
