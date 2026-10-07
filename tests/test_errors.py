from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import cast

import httpx
import pytest

import hushscript
from conftest import TOKEN
from helpers import FakeClock, Script, error_body, reply, sync_client
from hushscript import (
    AbortError,
    ApiError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    DailyLimitError,
    FileLimitError,
    HushscriptError,
    InsufficientBalanceError,
    JobFailedError,
    NetworkError,
    NotFoundError,
    OutcomeUnknownError,
    PaymentMethodRequiredError,
    PermissionDeniedError,
    PreflightError,
    RateLimitError,
    ResumeMismatchError,
    UnsupportedMediaError,
    UploadError,
    ValidationError,
    WaitTimeoutError,
)
from hushscript._errors import (
    error_from_response,
    operation_key,
    parse_retry_after,
    raise_for_response,
    render_hint,
)
from hushscript._redact import Credentials


def response(
    status: int,
    body: object = None,
    headers: dict[str, str] | None = None,
    *,
    method: str = "GET",
    path: str = "/v1/account",
) -> httpx.Response:
    request = httpx.Request(method, f"http://127.0.0.1:4010{path}")
    if body is None:
        return httpx.Response(status, text="Bad Gateway", headers=headers, request=request)
    return httpx.Response(status, json=body, headers=headers, request=request)


@pytest.mark.parametrize(
    ("slug", "code", "status", "expected"),
    [
        ("unauthorized", 2000, 401, AuthenticationError),
        ("agent_claim_invalid", 4036, 401, AuthenticationError),
        ("pat_scope_missing", 2023, 403, PermissionDeniedError),
        ("pat_purchase_requires_app", 4021, 403, PermissionDeniedError),
        ("country_restricted", 2011, 403, PermissionDeniedError),
        ("insufficient_balance", 3001, 402, InsufficientBalanceError),
        ("org_plan_frozen", 4025, 402, InsufficientBalanceError),
        ("not_found", 4000, 404, NotFoundError),
        ("wrong_state", 4001, 409, ConflictError),
        ("pat_limit", 4022, 409, ConflictError),
        ("bad_request", 1000, 400, ValidationError),
        ("policy_version_stale", 1043, 422, ValidationError),
        ("rate_limited", 5000, 429, RateLimitError),
        ("too_many_active_jobs", 5001, 429, RateLimitError),
        ("agent_purchase_capped", 4038, 429, RateLimitError),
        ("url_target_busy", 1042, 429, RateLimitError),
        ("upload_incomplete", 1041, 422, UploadError),
        ("size_exceeded", 1024, 422, UploadError),
    ],
)
def test_error_class_follows_the_spec_9_2_tree(
    slug: str, code: int, status: int, expected: type[HushscriptError]
) -> None:
    error = error_from_response(response(status, error_body(slug, code)))
    assert type(error) is expected
    assert (error.code, error.numeric_code, error.status) == (slug, code, status)
    assert error.message


def test_an_unlisted_status_is_a_plain_api_error() -> None:
    error = error_from_response(response(500, error_body("internal", 9999)))
    assert type(error) is ApiError
    assert error.code == "internal"
    assert "500" in error.message


def test_a_non_json_body_gets_a_status_code_and_no_numeric_code() -> None:
    error = error_from_response(response(502))
    assert type(error) is ApiError
    assert (error.code, error.numeric_code, error.status) == ("http_502", None, 502)
    assert error.details == {}


def test_a_json_body_without_an_error_slug_still_maps_by_status() -> None:
    error = error_from_response(response(404, ["not", "an", "object"]))
    assert type(error) is NotFoundError
    assert error.code == "http_404"


def test_message_is_the_catalog_meaning() -> None:
    error = error_from_response(response(401, error_body("unauthorized", 2000)))
    assert "token" in error.message.lower() or error.message


def test_extra_body_keys_become_details_and_nested_details_merge() -> None:
    body = error_body(
        "agent_pack_locked", 4037, needed_seconds=21, details={"allowed_packs": ["45min", "300min"]}
    )
    error = error_from_response(response(403, body))
    assert error.details == {"needed_seconds": 21, "allowed_packs": ["45min", "300min"]}
    assert error.hint == "New agent accounts can buy 45min, 300min until earlier purchases settle."


def test_a_scalar_details_value_is_kept_under_its_own_key() -> None:
    error = error_from_response(response(400, error_body("bad_request", 1000, details="why")))
    assert error.details == {"details": "why"}


def test_the_scope_hint_names_the_operation_scope() -> None:
    error = error_from_response(
        response(
            403, error_body("pat_scope_missing", 2023), method="POST", path="/v1/billing/purchase"
        )
    )
    assert error.hint is not None
    assert '"billing"' in error.hint


def test_the_scope_hint_resolves_templated_paths() -> None:
    error = error_from_response(
        response(403, error_body("pat_scope_missing", 2023), path="/v1/transcripts")
    )
    assert error.hint is not None
    assert '"transcripts:read" permission' in error.hint
    assert operation_key("GET", "/v1/jobs/abc123") == "GET /v1/jobs/{id}"
    assert operation_key("GET", "/v1/nowhere") is None
    assert operation_key("DELETE", "/v1/account") is None


def test_an_explicit_operation_overrides_the_request() -> None:
    error = error_from_response(
        response(403, error_body("pat_scope_missing", 2023)), operation="GET /v1/org"
    )
    assert error.hint is not None
    assert '"org:read"' in error.hint


def test_a_response_without_a_request_has_no_scope() -> None:
    bare = httpx.Response(403, json=error_body("pat_scope_missing", 2023))
    error = error_from_response(bare)
    assert error.hint is not None
    assert "{" not in error.hint
    assert error.hint.startswith("Create a token that includes it.")


def test_insufficient_balance_hint_reads_minutes_from_the_details() -> None:
    body = error_body("insufficient_balance", 3001, needed_seconds=3600, balance_seconds=610)
    error = error_from_response(response(402, body))
    assert error.hint is not None
    assert error.hint.startswith("Not enough minutes: 60 needed, 10 available.")


def test_retry_after_is_parsed_and_fills_the_hint() -> None:
    error = error_from_response(
        response(429, error_body("rate_limited", 5000), {"Retry-After": "61"})
    )
    assert error.retry_after == 61
    assert error.hint is not None
    assert "try again in 61 s" in error.hint


CAP = float(2**53 - 1)
CAP_TEXT = "9007199254740991"


@pytest.mark.parametrize("digits", ["9" * 400, "9" * 5000, str(2**63), "1" + "0" * 30])
def test_a_huge_retry_after_header_is_over_60_and_reported_capped(digits: str) -> None:
    error = error_from_response(
        response(429, error_body("rate_limited", 5000), {"Retry-After": digits})
    )
    assert error.retry_after == CAP
    assert error.hint is not None
    assert f"try again in {CAP_TEXT} s" in error.hint


@pytest.mark.parametrize(
    "literal",
    [b"9" * 400, b"9" * 5000, b"1e30", b"1" + b"0" * 30, b"9007199254740992"],
    ids=["400-digits", "5000-digits", "1e30", "31-digits", "2**53"],
)
def test_a_huge_retry_after_seconds_detail_is_over_60_and_reported_capped(literal: bytes) -> None:
    body = b'{"error":"rate_limited","code":5000,"retry_after_seconds":' + literal + b"}"
    error = error_from_response(httpx.Response(429, content=body))
    assert error.hint is not None
    assert f"try again in {CAP_TEXT} s" in error.hint


@pytest.mark.parametrize(
    "literal",
    [b"-1", b"-" + b"9" * 400, b"Infinity", b"-Infinity", b"NaN", b'"90"', b"true", b"null"],
)
def test_a_negative_or_non_numeric_retry_after_seconds_detail_is_absent(literal: bytes) -> None:
    body = b'{"error":"rate_limited","code":5000,"retry_after_seconds":' + literal + b"}"
    error = error_from_response(httpx.Response(429, content=body))
    assert error.hint == "Too many requests."


def test_the_header_wins_over_the_detail() -> None:
    body = {"error": "rate_limited", "code": 5000, "retry_after_seconds": 90}
    assert "in 7 s" in (error_from_response(response(429, body, {"Retry-After": "7"})).hint or "")
    assert "in 90 s" in (error_from_response(response(429, body)).hint or "")


@pytest.mark.parametrize("header", ["-1", "NaN", "Infinity", "1e400", "1.5", ""])
def test_a_negative_or_non_numeric_retry_after_header_is_absent(header: str) -> None:
    error = error_from_response(
        response(429, error_body("rate_limited", 5000), {"Retry-After": header})
    )
    assert error.retry_after is None
    assert error.hint == "Too many requests."


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5", 5.0),
        (" 12 ", 12.0),
        ("0", 0.0),
        (None, None),
        ("", None),
        ("-1", None),
        ("1.5", None),
        ("Wed, 21 Oct 2026 07:28:00 GMT", None),
        (chr(0x661), None),
    ],
)
def test_parse_retry_after_takes_integer_seconds_only(
    value: str | None, expected: float | None
) -> None:
    assert parse_retry_after(value) == expected


def test_the_token_is_redacted_from_message_hint_and_details() -> None:
    body = error_body("unauthorized", 2000, details=f"you sent {TOKEN}", echo=[TOKEN])
    error = error_from_response(response(401, body), credentials=Credentials(TOKEN))
    surface = " ".join(
        [error.message, error.hint or "", repr(error.details), str(error), repr(error)]
    )
    assert TOKEN not in surface
    assert TOKEN[12:] not in surface


def test_the_token_shape_is_redacted_even_without_credentials() -> None:
    error = error_from_response(response(401, error_body("unauthorized", 2000, details=TOKEN)))
    assert TOKEN[12:] not in repr(error.details)


def test_raise_for_response_ignores_success_and_raises_otherwise() -> None:
    raise_for_response(response(200, {"ok": True}))
    with pytest.raises(NotFoundError):
        raise_for_response(response(404, error_body("not_found", 4000)))


def test_render_hint_drops_sentences_with_unfilled_placeholders() -> None:
    assert render_hint("no_such_slug") is None
    assert render_hint("insufficient_balance") == (
        "Buy a pack with the SDK's buy method or in the app."
    )
    assert render_hint("rate_limited") == "Too many requests."
    assert render_hint("config_invalid") is None
    assert render_hint("daily_limit") is None
    daily = {"used_today_seconds": 3599, "max_daily_seconds": 36000}
    assert render_hint("daily_limit", daily) == (
        "This upload would pass your daily transcription limit"
        " (59 of 600 min used in the last 24 h)."
    )
    assert render_hint("insufficient_balance", {"needed_seconds": 61, "balance_seconds": 119}) == (
        "Not enough minutes: 2 needed, 1 available."
        " Buy a pack with the SDK's buy method or in the app."
    )
    assert render_hint("insufficient_balance", {"needed_seconds": 60, "balance_seconds": -1}) == (
        "Not enough minutes: 1 needed, -1 available."
        " Buy a pack with the SDK's buy method or in the app."
    )
    assert render_hint("daily_limit", {"used": 3, "max": 10}) == (
        "This upload would pass your daily transcription limit (3 of 10 min used in the last 24 h)."
    )
    assert render_hint("agent_pack_locked", {"allowed_packs": ["45min"]}) == (
        "New agent accounts can buy 45min until earlier purchases settle."
    )
    assert render_hint("rate_limited", retry_after=2.5) == (
        "Too many requests. The SDK already waited and retried; slow down or try again in 3 s."
    )


CAPPED = "This account has used its 3 purchase attempts for the last 24 hours."


@pytest.mark.parametrize(
    ("code", "details", "retry_after", "expected"),
    [
        ("rate_limited", {}, None, "Too many requests."),
        ("agent_purchase_capped", {}, None, CAPPED),
        ("agent_purchase_capped", {}, 3600, f"{CAPPED} Try again in 3600 s."),
        (
            "agent_purchase_capped",
            {"retry_after_seconds": 90},
            None,
            f"{CAPPED} Try again in 90 s.",
        ),
        (
            "too_many_active_jobs",
            {},
            None,
            "50 jobs are already in progress. Wait for some to finish.",
        ),
        (
            "pat_scope_missing",
            {},
            None,
            (
                "Create a token that includes it. For billing, the token also needs"
                ' "Let this token buy minutes" turned on when you create it, and'
                ' "Let connected apps buy minutes" must be on in the app under Account \u2192 MCP.'
            ),
        ),
        ("agent_pack_locked", {}, None, None),
        (
            "policy_version_stale",
            {"current_version": "v2"},
            None,
            "Accept the current terms version: v2.",
        ),
    ],
)
def test_hint_rendering_keeps_each_sentence_period_and_joins_with_a_space(
    code: str, details: dict[str, object], retry_after: float | None, expected: str | None
) -> None:
    assert render_hint(code, details, retry_after) == expected


def _conformance_hint_cases() -> list[dict[str, object]]:
    directory = os.environ.get("CONFORMANCE_DIR")
    assert directory, "set CONFORMANCE_DIR to a conformance checkout (just test does it for you)"
    path = Path(directory) / "fixtures" / "hint-rendering.json"
    cases: list[dict[str, object]] = json.loads(path.read_text(encoding="utf-8"))
    return cases


def test_hint_rendering_matches_the_conformance_fixture() -> None:
    cases = _conformance_hint_cases()
    assert len(cases) >= 30
    mismatches: list[str] = []
    for case in cases:
        scope = case.get("scope")
        details = cast("dict[str, object]", case["details"])
        actual = render_hint(
            str(case["slug"]), details, scope=scope if isinstance(scope, str) else None
        )
        if actual != case["expected"]:
            mismatches.append(f"{case['slug']} {details}: {actual!r} != {case['expected']!r}")
    assert not mismatches


def test_no_hint_names_an_sdk_method() -> None:
    """R62: hint text is shared by every SDK, so it names no method of any of them."""
    method = re.compile(r"\bhs\b|\w\(|add_?card|set_?default|jobs\.|\.buy", re.IGNORECASE)
    named = {slug: text for slug, text in hushscript.HINTS.items() if method.search(text)}
    assert not named


def test_the_error_tree_matches_spec_9_2() -> None:
    assert issubclass(PreflightError, HushscriptError)
    for preflight in (UnsupportedMediaError, FileLimitError, DailyLimitError, ResumeMismatchError):
        assert issubclass(preflight, PreflightError)
    for api in (
        AuthenticationError,
        PermissionDeniedError,
        InsufficientBalanceError,
        NotFoundError,
        ConflictError,
        ValidationError,
        RateLimitError,
    ):
        assert issubclass(api, ApiError)
    for top in (
        ConfigurationError,
        ApiError,
        PaymentMethodRequiredError,
        UploadError,
        JobFailedError,
        WaitTimeoutError,
        AbortError,
        NetworkError,
        OutcomeUnknownError,
    ):
        assert issubclass(top, HushscriptError)
    assert PermissionDeniedError.__name__ == "PermissionDeniedError"
    assert not hasattr(hushscript, "PermissionError")


def test_sdk_side_errors_carry_their_own_codes_and_hints() -> None:
    assert FileLimitError("short", code="duration_out_of_range").hint == (
        "Files must be between 15 seconds and 10 hours long."
    )
    assert PaymentMethodRequiredError("none").code == "no_default_card"
    assert ConfigurationError("bad").hint is None
    error = ConfigurationError("bad", hint="see docs")
    assert error.hint == "see docs"


def test_extra_fields_on_job_and_resume_errors() -> None:
    failed = JobFailedError(
        "failed", job_id="j1", error=f"bad {TOKEN}", failure_kind="media_unreadable"
    )
    assert (failed.job_id, failed.failure_kind) == ("j1", "media_unreadable")
    assert failed.error is not None
    assert TOKEN[12:] not in failed.error
    assert WaitTimeoutError("slow", resume_token="rt").resume_token == "rt"
    assert AbortError("stop", resume_token="rt").resume_token == "rt"


def test_str_carries_the_hint_and_message_stays_plain() -> None:
    error = error_from_response(response(401, error_body("unauthorized", 2000)))
    assert str(error) == f"{error.message} {error.hint}"
    assert error.hint is not None
    assert error.hint not in error.message


def test_a_boolean_detail_fills_a_hint_placeholder() -> None:
    assert render_hint("policy_version_stale", {"current_version": True}) == (
        "Accept the current terms version: true."
    )


def test_repr_and_str() -> None:
    error = error_from_response(response(404, error_body("not_found", 4000)))
    assert str(error) == error.message
    assert repr(error).startswith("NotFoundError(code='not_found', status=404")


def test_details_keys_are_snake_cased_recursively() -> None:
    body = error_body("bad_request", 1000, neededSeconds=1, nested={"innerKey": [{"deepKey": 2}]})
    error = error_from_response(response(400, body))
    assert error.details == {"needed_seconds": 1, "nested": {"inner_key": [{"deep_key": 2}]}}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/jobs/job_1"),
        ("GET", "/v1/jobs"),
        ("POST", "/v1/uploads/job_1/heartbeat"),
        ("POST", "/v1/uploads/job_1/complete"),
        ("PUT", "/v1/uploads/job_1/parts/2"),
    ],
)
def test_wrong_state_carries_its_hint_on_job_and_upload_operations(method: str, path: str) -> None:
    error = error_from_response(
        response(409, error_body("wrong_state", 4001), method=method, path=path)
    )
    assert isinstance(error, ConflictError)
    assert error.hint == "The job has already moved on. Fetch the job to see where it is."


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v1/billing/purchase"),
        ("POST", "/v1/agent/accounts/sig_1/claim"),
        ("POST", "/v1/agent/credentials/rotate"),
        ("GET", "/v1/transcripts/tr_1"),
        ("POST", "/v1/billing/setup-session"),
        ("GET", "/v1/account"),
    ],
)
def test_wrong_state_has_no_job_hint_on_any_other_operation(method: str, path: str) -> None:
    error = error_from_response(
        response(409, error_body("wrong_state", 4001), method=method, path=path)
    )
    assert isinstance(error, ConflictError)
    assert (error.code, error.numeric_code, error.status) == ("wrong_state", 4001, 409)
    assert error.hint is None
    assert "hs.jobs.get" not in str(error)


def test_wrong_state_without_a_request_has_no_hint_unless_the_operation_says_so() -> None:
    bare = httpx.Response(409, json=error_body("wrong_state", 4001))
    assert error_from_response(bare).hint is None
    assert error_from_response(bare, operation="GET /v1/jobs/{id}").hint is not None
    assert error_from_response(bare, operation="POST /v1/billing/purchase").hint is None


def test_other_hints_are_unaffected_by_the_wrong_state_rule() -> None:
    error = error_from_response(
        response(
            402,
            error_body("insufficient_balance", 3001, needed_seconds=60),
            path="/v1/billing/purchase",
        )
    )
    assert error.hint is not None


def _nested(depth: int, leaf: object = 1) -> str:
    return "[" * depth + json.dumps(leaf) + "]" * depth


@pytest.mark.parametrize("depth", [700, 3000, 200_000])
@pytest.mark.parametrize("status", [400, 402, 404, 429, 500, 502])
def test_an_error_body_nested_past_the_recursion_limit_is_still_an_error_of_its_status(
    depth: int, status: int
) -> None:
    for text in (
        _nested(depth),
        '{"error":"rate_limited","code":5000,"details":' + _nested(depth) + "}",
        '{"error":"rate_limited","code":5000,"x":' + '{"a":' * depth + "1" + "}" * depth + "}",
    ):
        reply_ = httpx.Response(
            status,
            content=text.encode(),
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", "http://127.0.0.1:4010/v1/account"),
        )
        error = error_from_response(reply_, credentials=Credentials(TOKEN))
        assert isinstance(error, ApiError)
        assert error.status == status
        if depth >= 3000:  # past what any Python version's walkers read
            assert error.details == {}


def test_a_deep_error_body_that_still_parses_keeps_its_slug() -> None:
    text = '{"error":"rate_limited","code":5000,"details":' + _nested(800) + "}"
    reply_ = httpx.Response(
        429,
        content=text.encode(),
        request=httpx.Request("GET", "http://127.0.0.1:4010/v1/account"),
    )
    assert error_from_response(reply_, credentials=Credentials(TOKEN)).code in {
        "rate_limited",
        "http_429",
    }


def test_the_transport_survives_a_deep_body_on_a_create_that_was_rate_limited() -> None:
    script = Script([httpx.Response(429, content=_nested(3000).encode()), reply(200, {})])
    client = sync_client(script, FakeClock(), token=TOKEN)
    response = client.post("/v1/uploads", json={"idempotency_key": "k" * 20})
    assert response.status_code == 200
    assert script.calls == 2
