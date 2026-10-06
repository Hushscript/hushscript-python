from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.agent_claim_request import AgentClaimRequest
from ...models.agent_claim_response import AgentClaimResponse
from ...models.error import Error
from ...types import Response


def _get_kwargs(
    signup_id: str,
    *,
    body: AgentClaimRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/agent/accounts/{signup_id}/claim".format(
            signup_id=quote(str(signup_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AgentClaimResponse | Error | None:
    if response.status_code == 201:
        response_201 = AgentClaimResponse.from_dict(response.json())

        return response_201

    if response.status_code == 400:
        response_400 = Error.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = Error.from_dict(response.json())

        return response_401

    if response.status_code == 409:
        response_409 = Error.from_dict(response.json())

        return response_409

    if response.status_code == 429:
        response_429 = Error.from_dict(response.json())

        return response_429

    if response.status_code == 500:
        response_500 = Error.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[AgentClaimResponse | Error]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    signup_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: AgentClaimRequest,
) -> Response[AgentClaimResponse | Error]:
    """Claim a paid agent signup into a real account

     Exchanges a paid, unclaimed agent signup for the account it pays for. Presents the claim_secret
    returned once by POST /v1/agent/accounts; a wrong secret, an unknown signup_id, an already claimed
    signup, a refunded signup, and an expired signup all answer the identical agent_claim_invalid error
    so a caller can never learn which of those is true. Only once that secret checks out does payment
    state matter: a signup whose Checkout Session has not settled to paid answers wrong_state instead. A
    successful claim is single use; creates exactly one account with a synthetic, unresolvable login
    identity; grants the paid pack once, never twice, even on a retried request; and mints exactly one
    personal access token with the account's own agent scopes, returned only in this response.

    Args:
        signup_id (str):
        body (AgentClaimRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AgentClaimResponse | Error]
    """

    kwargs = _get_kwargs(
        signup_id=signup_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    signup_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: AgentClaimRequest,
) -> AgentClaimResponse | Error | None:
    """Claim a paid agent signup into a real account

     Exchanges a paid, unclaimed agent signup for the account it pays for. Presents the claim_secret
    returned once by POST /v1/agent/accounts; a wrong secret, an unknown signup_id, an already claimed
    signup, a refunded signup, and an expired signup all answer the identical agent_claim_invalid error
    so a caller can never learn which of those is true. Only once that secret checks out does payment
    state matter: a signup whose Checkout Session has not settled to paid answers wrong_state instead. A
    successful claim is single use; creates exactly one account with a synthetic, unresolvable login
    identity; grants the paid pack once, never twice, even on a retried request; and mints exactly one
    personal access token with the account's own agent scopes, returned only in this response.

    Args:
        signup_id (str):
        body (AgentClaimRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AgentClaimResponse | Error
    """

    return sync_detailed(
        signup_id=signup_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    signup_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: AgentClaimRequest,
) -> Response[AgentClaimResponse | Error]:
    """Claim a paid agent signup into a real account

     Exchanges a paid, unclaimed agent signup for the account it pays for. Presents the claim_secret
    returned once by POST /v1/agent/accounts; a wrong secret, an unknown signup_id, an already claimed
    signup, a refunded signup, and an expired signup all answer the identical agent_claim_invalid error
    so a caller can never learn which of those is true. Only once that secret checks out does payment
    state matter: a signup whose Checkout Session has not settled to paid answers wrong_state instead. A
    successful claim is single use; creates exactly one account with a synthetic, unresolvable login
    identity; grants the paid pack once, never twice, even on a retried request; and mints exactly one
    personal access token with the account's own agent scopes, returned only in this response.

    Args:
        signup_id (str):
        body (AgentClaimRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AgentClaimResponse | Error]
    """

    kwargs = _get_kwargs(
        signup_id=signup_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    signup_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: AgentClaimRequest,
) -> AgentClaimResponse | Error | None:
    """Claim a paid agent signup into a real account

     Exchanges a paid, unclaimed agent signup for the account it pays for. Presents the claim_secret
    returned once by POST /v1/agent/accounts; a wrong secret, an unknown signup_id, an already claimed
    signup, a refunded signup, and an expired signup all answer the identical agent_claim_invalid error
    so a caller can never learn which of those is true. Only once that secret checks out does payment
    state matter: a signup whose Checkout Session has not settled to paid answers wrong_state instead. A
    successful claim is single use; creates exactly one account with a synthetic, unresolvable login
    identity; grants the paid pack once, never twice, even on a retried request; and mints exactly one
    personal access token with the account's own agent scopes, returned only in this response.

    Args:
        signup_id (str):
        body (AgentClaimRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AgentClaimResponse | Error
    """

    return (
        await asyncio_detailed(
            signup_id=signup_id,
            client=client,
            body=body,
        )
    ).parsed
