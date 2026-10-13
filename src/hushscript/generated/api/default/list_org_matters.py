from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.list_org_matters_status import (
    ListOrgMattersStatus,
)
from ...models.org_matters_response import OrgMattersResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    status: ListOrgMattersStatus | Unset = "open",
    q: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_status: str | Unset = UNSET
    if not isinstance(status, Unset):
        json_status = status

    params["status"] = json_status

    params["q"] = q

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/matters",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | OrgMattersResponse | None:
    if response.status_code == 200:
        response_200 = OrgMattersResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = Error.from_dict(response.json())

        return response_400

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
) -> Response[Error | OrgMattersResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    status: ListOrgMattersStatus | Unset = "open",
    q: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Response[Error | OrgMattersResponse]:
    """List the caller's organization's matter registry

     Returns up to 200 rows of the caller's organization's matter registry, ordered by code. Membership
    gated, not admin only: a member filing a transcript under an existing matter is offered this same
    list. Every row here is {id, code, status} for every caller, including an admin's own token -- the
    client a matter belongs to is /api admin only: GET /api/org/matters publishes client_id and the
    client's own code to an admin caller there, but this /v1 route never does, for any caller.

    Args:
        status (ListOrgMattersStatus | Unset):  Default: 'open'.
        q (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | OrgMattersResponse]
    """

    kwargs = _get_kwargs(
        status=status,
        q=q,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    status: ListOrgMattersStatus | Unset = "open",
    q: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Error | OrgMattersResponse | None:
    """List the caller's organization's matter registry

     Returns up to 200 rows of the caller's organization's matter registry, ordered by code. Membership
    gated, not admin only: a member filing a transcript under an existing matter is offered this same
    list. Every row here is {id, code, status} for every caller, including an admin's own token -- the
    client a matter belongs to is /api admin only: GET /api/org/matters publishes client_id and the
    client's own code to an admin caller there, but this /v1 route never does, for any caller.

    Args:
        status (ListOrgMattersStatus | Unset):  Default: 'open'.
        q (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | OrgMattersResponse
    """

    return sync_detailed(
        client=client,
        status=status,
        q=q,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    status: ListOrgMattersStatus | Unset = "open",
    q: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Response[Error | OrgMattersResponse]:
    """List the caller's organization's matter registry

     Returns up to 200 rows of the caller's organization's matter registry, ordered by code. Membership
    gated, not admin only: a member filing a transcript under an existing matter is offered this same
    list. Every row here is {id, code, status} for every caller, including an admin's own token -- the
    client a matter belongs to is /api admin only: GET /api/org/matters publishes client_id and the
    client's own code to an admin caller there, but this /v1 route never does, for any caller.

    Args:
        status (ListOrgMattersStatus | Unset):  Default: 'open'.
        q (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | OrgMattersResponse]
    """

    kwargs = _get_kwargs(
        status=status,
        q=q,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    status: ListOrgMattersStatus | Unset = "open",
    q: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Error | OrgMattersResponse | None:
    """List the caller's organization's matter registry

     Returns up to 200 rows of the caller's organization's matter registry, ordered by code. Membership
    gated, not admin only: a member filing a transcript under an existing matter is offered this same
    list. Every row here is {id, code, status} for every caller, including an admin's own token -- the
    client a matter belongs to is /api admin only: GET /api/org/matters publishes client_id and the
    client's own code to an admin caller there, but this /v1 route never does, for any caller.

    Args:
        status (ListOrgMattersStatus | Unset):  Default: 'open'.
        q (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | OrgMattersResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            status=status,
            q=q,
            limit=limit,
        )
    ).parsed
