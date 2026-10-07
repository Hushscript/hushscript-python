from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from hushscript._config import acceptable_token
from hushscript._errors import (
    OutcomeUnknownError,
    ValidationError,
    raise_for_response,
)
from hushscript._http import UNKNOWN_HINTS
from hushscript._json import as_dict, as_list
from hushscript._response import bad_response, parsed
from hushscript._retry import CLAIM, ROTATE
from hushscript._shape import INT_LIMIT, as_text, as_whole, check_shape, to_datetime
from hushscript._shapes import AGENT_SIGNUP
from hushscript.money import Money, to_money
from hushscript.resources._params import path_id
from hushscript.resources.account import Balance, minutes_of

if TYPE_CHECKING:
    from datetime import datetime

    import httpx

    from hushscript._redact import Credentials
    from hushscript.transcribe.session import AsyncSession, SyncSession

CLAIM_ROUTE: Final = "POST /v1/agent/accounts/{signup_id}/claim"
ROTATE_ROUTE: Final = "POST /v1/agent/credentials/rotate"


@dataclass(frozen=True, slots=True)
class AgentInfo:
    """The agent an account is opened for."""

    name: str
    platform: str
    contact_url: str | None = None


@dataclass(frozen=True, slots=True)
class AgentSignup:
    """What `agent_signup` returns."""

    signup_id: str
    """Passed back to `agent_claim` verbatim."""
    claim_secret: str
    """Shown once; `agent_claim` needs it."""
    checkout_url: str
    """The hosted checkout page where the account is paid for; it expires at `expires_at`."""
    price: Money
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AgentAccount:
    """What `agent_claim` returns."""

    token: str
    """The account's token, shown once: write it down before anything else can fail."""
    user_id: str
    scopes: list[str]
    balance: Balance
    """The pack just granted. A new account holds nothing and has no expiry in the answer."""

    __hash__ = None  # type: ignore[assignment]  # holds a list, so it is unhashable by design


@dataclass(frozen=True, slots=True)
class RotatedToken:
    """What `rotate_token` returns."""

    token: str
    """The successor token, shown once; the client already sends it."""
    token_id: str
    scopes: list[str]
    expires_at: datetime | None
    """None when the token never expires."""

    __hash__ = None  # type: ignore[assignment]  # holds a list, so it is unhashable by design


def accept_terms_required() -> ValidationError:
    return ValidationError(
        "accept_terms is required: pass the policy version you accept. "
        "It is never filled in for you.",
        code="accept_terms_required",
    )


def check_accept_terms(accept_terms: object) -> str:
    if not isinstance(accept_terms, str) or not accept_terms.strip():
        raise accept_terms_required()
    return accept_terms


def signup_body(  # mirrors the keyword surface of `agent_signup`
    *,
    email: str,
    pack: str,
    accept_terms: str,
    agent: AgentInfo,
    data_region: str | None,
    dry_run: bool,
) -> dict[str, object]:
    who: dict[str, object] = {"name": agent.name, "platform": agent.platform}
    if agent.contact_url is not None:
        who["contact_url"] = agent.contact_url
    body: dict[str, object] = {
        "contact_email": email,
        "pack_id": pack,
        "accept_terms_version": accept_terms,
        "agent": who,
    }
    if data_region is not None:
        body["data_region"] = data_region
    if dry_run:
        body["dry_run"] = True
    return body


def signup_of(body: object) -> AgentSignup:
    check_shape(body, AGENT_SIGNUP, "signup response")
    fields = as_dict(body) or {}
    return AgentSignup(
        signup_id=as_text(fields["signup_id"]),
        claim_secret=as_text(fields["claim_secret"]),
        checkout_url=as_text(fields["checkout_url"]),
        price=to_money(as_whole(fields["amount"]), as_text(fields["currency"])),
        expires_at=to_datetime(fields["expires_at"]),
    )


def _strings(value: object) -> list[str] | None:
    items = as_list(value)
    if items is None or not all(isinstance(item, str) for item in items):
        return None
    return [as_text(item) for item in items]


def _whole(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _count(value: object) -> bool:
    return _whole(value) and isinstance(value, int) and 0 <= value < INT_LIMIT


def _claim_usable(fields: dict[str, object]) -> bool:
    return (
        isinstance(fields.get("user_id"), str)
        and _strings(fields.get("scopes")) is not None
        and _count(fields.get("balance_seconds"))
    )


def _expiry_usable(fields: dict[str, object]) -> bool:
    expires = fields.get("expires_at")
    return expires is None or (
        _whole(expires) and isinstance(expires, int) and 0 <= expires <= _MAX_SECONDS
    )


_MAX_SECONDS: Final = 253_402_300_799


def _rotate_usable(fields: dict[str, object]) -> bool:
    return (
        isinstance(fields.get("pat_id"), str)
        and _strings(fields.get("scopes")) is not None
        and _expiry_usable(fields)
    )


def _decode(response: httpx.Response) -> dict[str, object]:
    try:
        return as_dict(response.json()) or {}
    except (ValueError, RecursionError):
        return {}


def lost_credential(  # one place that builds the spec 7.4 error
    response: httpx.Response, route: str, hint_key: str, seen: str | None, credentials: Credentials
) -> OutcomeUnknownError:
    """A claim or rotation answered 2xx without a usable credential: it was minted and may be
    lost, exactly as if the answer never arrived (spec 7.4). `seen` is whatever the answer carried
    in its `pat` field, kept on the error so it is not lost."""
    failure = OutcomeUnknownError(
        credentials.scrub(f"The answer to {route} could not be used, so the token may be lost."),
        hint=UNKNOWN_HINTS[hint_key],
        received_token=seen,
    )
    failure.__cause__ = bad_response(response, "credential response")
    return failure


def read_answer(
    response: httpx.Response, credentials: Credentials
) -> tuple[dict[str, object], str | None]:
    """The fields and the `pat` of a claim or rotation answer; a non-2xx answer raises its API
    error. A 2xx is decoded whatever its status, and the token it carried is scrubbed from every
    text from now on, trimmed."""
    raise_for_response(response, credentials=credentials)
    fields = _decode(response)
    pat = fields.get("pat")
    seen = pat if isinstance(pat, str) else None
    if seen is not None:
        credentials.remember(seen.strip())
    return fields, seen


def account_of(token: str, fields: dict[str, object]) -> AgentAccount:
    seconds = as_whole(fields["balance_seconds"])
    return AgentAccount(
        token=token,
        user_id=as_text(fields["user_id"]),
        scopes=_strings(fields["scopes"]) or [],
        balance=Balance(
            seconds=seconds,
            minutes=minutes_of(seconds),
            held_seconds=0,
            expires_at=None,
            purchases_remaining=None,
        ),
    )


def rotated_of(token: str, fields: dict[str, object]) -> RotatedToken:
    expires = fields.get("expires_at")
    return RotatedToken(
        token=token,
        token_id=as_text(fields["pat_id"]),
        scopes=_strings(fields["scopes"]) or [],
        expires_at=None if expires is None else to_datetime(expires),
    )


def claim_path(signup_id: object) -> str:
    return f"/v1/agent/accounts/{path_id(signup_id)}/claim"


def claim_body(claim_secret: str) -> dict[str, object]:
    return {"claim_secret": claim_secret}


def signed_up(response: httpx.Response, credentials: Credentials) -> AgentSignup:
    return parsed(response, credentials, signup_of)


def claimed(response: httpx.Response, credentials: Credentials) -> AgentAccount:
    fields, seen = read_answer(response, credentials)
    if seen is None or not acceptable_token(seen) or not _claim_usable(fields):
        raise lost_credential(response, CLAIM_ROUTE, CLAIM, seen, credentials)
    return account_of(seen, fields)


def rotated(response: httpx.Response, credentials: Credentials) -> RotatedToken:
    """The rotation answer. The server revoked the old token when it answered 2xx, so a token that
    passes the token check is the one the client sends from then on (spec 7.4), whatever else is
    wrong with the answer. The one exception is an expiry that cannot be read, as in the TypeScript
    SDK: the answer is then not trusted at all, the old token stays in use and the new one is only
    kept on the error."""
    fields, seen = read_answer(response, credentials)
    token_usable = seen is not None and acceptable_token(seen)
    if seen is not None and token_usable and _expiry_usable(fields):
        credentials.replace(seen)
    if seen is None or not token_usable or not _rotate_usable(fields):
        raise lost_credential(response, ROTATE_ROUTE, ROTATE, seen, credentials)
    return rotated_of(seen, fields)


class Agent:
    """`hs.agent`: the calls an agent account makes with its own token."""

    def __init__(self, session: SyncSession) -> None:
        self._session = session

    def rotate_token(self) -> RotatedToken:
        """Mints a successor token and revokes the one in use. The client sends the new token from
        then on, to retries already queued as well; store the returned one right away. It is never
        retried: a lost answer, or one without a usable token, is an `OutcomeUnknownError` whose
        hint says what to check, and the client keeps its old token then."""
        response = self._session.http.post("/v1/agent/credentials/rotate")
        return rotated(response, self._session.credentials)


class AsyncAgent:
    """`hs.agent` on the asyncio client."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def rotate_token(self) -> RotatedToken:
        response = await self._session.http.post("/v1/agent/credentials/rotate")
        return rotated(response, self._session.credentials)
