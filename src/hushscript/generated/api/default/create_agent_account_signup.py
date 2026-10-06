from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.agent_signup_request import AgentSignupRequest
from ...models.agent_signup_response import AgentSignupResponse
from ...models.error import Error
from ...types import Response


def _get_kwargs(
    *,
    body: AgentSignupRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/agent/accounts",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AgentSignupResponse | Error | None:
    if response.status_code == 200:
        response_200 = AgentSignupResponse.from_dict(response.json())

        return response_200

    if response.status_code == 201:
        response_201 = AgentSignupResponse.from_dict(response.json())

        return response_201

    if response.status_code == 400:
        response_400 = Error.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = Error.from_dict(response.json())

        return response_403

    if response.status_code == 409:
        response_409 = Error.from_dict(response.json())

        return response_409

    if response.status_code == 422:
        response_422 = Error.from_dict(response.json())

        return response_422

    if response.status_code == 429:
        response_429 = Error.from_dict(response.json())

        return response_429

    if response.status_code == 500:
        response_500 = Error.from_dict(response.json())

        return response_500

    if response.status_code == 502:
        response_502 = Error.from_dict(response.json())

        return response_502

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[AgentSignupResponse | Error]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: AgentSignupRequest,
) -> Response[AgentSignupResponse | Error]:
    """Start a headless, payment-first account signup

     Opens a hosted Stripe Checkout Session for a payment-first, headless account signup. No account and
    no session cookie exist yet: complete checkout_url with your own browser automation, then claim the
    account with claim_secret at POST /v1/agent/accounts/{signup_id}/claim. Every field is validated
    before any Stripe call, followed by the same restricted-jurisdiction and allowlist gates the human
    signup paths apply. accept_terms_version must equal the server's current policy version, returned in
    the policy_version_stale error when it does not match. pack selects a minute pack by id; amount and
    currency come back server derived and must never be sent in the request. data_region is derived from
    your network location and an optional hint is honored only when it agrees with that derivation.
    signup_id is region-prefixed (hsr1:<region>:<id>) and must be presented back verbatim to the claim
    route, so the request reaches the same regional backend that holds the row. Set dry_run to true to
    validate the request and get back a synthetic 200 response with no Stripe session created and no
    charge possible, for rehearsing the shape before spending real money; a dry run signup_id is never
    region-prefixed and can never be claimed.

    Args:
        body (AgentSignupRequest): The client must never supply amount: it is derived server side
            from pack.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AgentSignupResponse | Error]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: AgentSignupRequest,
) -> AgentSignupResponse | Error | None:
    """Start a headless, payment-first account signup

     Opens a hosted Stripe Checkout Session for a payment-first, headless account signup. No account and
    no session cookie exist yet: complete checkout_url with your own browser automation, then claim the
    account with claim_secret at POST /v1/agent/accounts/{signup_id}/claim. Every field is validated
    before any Stripe call, followed by the same restricted-jurisdiction and allowlist gates the human
    signup paths apply. accept_terms_version must equal the server's current policy version, returned in
    the policy_version_stale error when it does not match. pack selects a minute pack by id; amount and
    currency come back server derived and must never be sent in the request. data_region is derived from
    your network location and an optional hint is honored only when it agrees with that derivation.
    signup_id is region-prefixed (hsr1:<region>:<id>) and must be presented back verbatim to the claim
    route, so the request reaches the same regional backend that holds the row. Set dry_run to true to
    validate the request and get back a synthetic 200 response with no Stripe session created and no
    charge possible, for rehearsing the shape before spending real money; a dry run signup_id is never
    region-prefixed and can never be claimed.

    Args:
        body (AgentSignupRequest): The client must never supply amount: it is derived server side
            from pack.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AgentSignupResponse | Error
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: AgentSignupRequest,
) -> Response[AgentSignupResponse | Error]:
    """Start a headless, payment-first account signup

     Opens a hosted Stripe Checkout Session for a payment-first, headless account signup. No account and
    no session cookie exist yet: complete checkout_url with your own browser automation, then claim the
    account with claim_secret at POST /v1/agent/accounts/{signup_id}/claim. Every field is validated
    before any Stripe call, followed by the same restricted-jurisdiction and allowlist gates the human
    signup paths apply. accept_terms_version must equal the server's current policy version, returned in
    the policy_version_stale error when it does not match. pack selects a minute pack by id; amount and
    currency come back server derived and must never be sent in the request. data_region is derived from
    your network location and an optional hint is honored only when it agrees with that derivation.
    signup_id is region-prefixed (hsr1:<region>:<id>) and must be presented back verbatim to the claim
    route, so the request reaches the same regional backend that holds the row. Set dry_run to true to
    validate the request and get back a synthetic 200 response with no Stripe session created and no
    charge possible, for rehearsing the shape before spending real money; a dry run signup_id is never
    region-prefixed and can never be claimed.

    Args:
        body (AgentSignupRequest): The client must never supply amount: it is derived server side
            from pack.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AgentSignupResponse | Error]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: AgentSignupRequest,
) -> AgentSignupResponse | Error | None:
    """Start a headless, payment-first account signup

     Opens a hosted Stripe Checkout Session for a payment-first, headless account signup. No account and
    no session cookie exist yet: complete checkout_url with your own browser automation, then claim the
    account with claim_secret at POST /v1/agent/accounts/{signup_id}/claim. Every field is validated
    before any Stripe call, followed by the same restricted-jurisdiction and allowlist gates the human
    signup paths apply. accept_terms_version must equal the server's current policy version, returned in
    the policy_version_stale error when it does not match. pack selects a minute pack by id; amount and
    currency come back server derived and must never be sent in the request. data_region is derived from
    your network location and an optional hint is honored only when it agrees with that derivation.
    signup_id is region-prefixed (hsr1:<region>:<id>) and must be presented back verbatim to the claim
    route, so the request reaches the same regional backend that holds the row. Set dry_run to true to
    validate the request and get back a synthetic 200 response with no Stripe session created and no
    charge possible, for rehearsing the shape before spending real money; a dry run signup_id is never
    region-prefixed and can never be claimed.

    Args:
        body (AgentSignupRequest): The client must never supply amount: it is derived server side
            from pack.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AgentSignupResponse | Error
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
