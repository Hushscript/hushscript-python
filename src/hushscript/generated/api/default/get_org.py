from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.org_summary_response import OrgSummaryResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | OrgSummaryResponse | None:
    if response.status_code == 200:
        response_200 = OrgSummaryResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = Error.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = Error.from_dict(response.json())

        return response_403

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
) -> Response[Error | OrgSummaryResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[Error | OrgSummaryResponse]:
    """Read the caller's organization summary

     A pure passthrough of GET /api/org's body: plan state and term, pool balance and expiry, retention
    policy, tax id, auto-renewal source and failure count, the workspace-wide default per-member cap,
    and the caller's own effective cap and month-to-date spend against the pool. Membership only, not
    admin -- renewal_user_id is visible to admins only.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | OrgSummaryResponse]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> Error | OrgSummaryResponse | None:
    """Read the caller's organization summary

     A pure passthrough of GET /api/org's body: plan state and term, pool balance and expiry, retention
    policy, tax id, auto-renewal source and failure count, the workspace-wide default per-member cap,
    and the caller's own effective cap and month-to-date spend against the pool. Membership only, not
    admin -- renewal_user_id is visible to admins only.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | OrgSummaryResponse
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[Error | OrgSummaryResponse]:
    """Read the caller's organization summary

     A pure passthrough of GET /api/org's body: plan state and term, pool balance and expiry, retention
    policy, tax id, auto-renewal source and failure count, the workspace-wide default per-member cap,
    and the caller's own effective cap and month-to-date spend against the pool. Membership only, not
    admin -- renewal_user_id is visible to admins only.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | OrgSummaryResponse]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> Error | OrgSummaryResponse | None:
    """Read the caller's organization summary

     A pure passthrough of GET /api/org's body: plan state and term, pool balance and expiry, retention
    policy, tax id, auto-renewal source and failure count, the workspace-wide default per-member cap,
    and the caller's own effective cap and month-to-date spend against the pool. Membership only, not
    admin -- renewal_user_id is visible to admins only.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | OrgSummaryResponse
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
