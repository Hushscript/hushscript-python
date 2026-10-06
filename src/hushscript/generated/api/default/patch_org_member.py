from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.patch_org_member_body import PatchOrgMemberBody
from ...models.patch_org_member_response_200 import PatchOrgMemberResponse200
from ...types import Response


def _get_kwargs(
    user_id: str,
    *,
    body: PatchOrgMemberBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/org/members/{user_id}".format(
            user_id=quote(str(user_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | PatchOrgMemberResponse200 | None:
    if response.status_code == 200:
        response_200 = PatchOrgMemberResponse200.from_dict(response.json())

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

    if response.status_code == 404:
        response_404 = Error.from_dict(response.json())

        return response_404

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

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Error | PatchOrgMemberResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    user_id: str,
    *,
    client: AuthenticatedClient,
    body: PatchOrgMemberBody,
) -> Response[Error | PatchOrgMemberResponse200]:
    """Change a workspace member's rights or cap

     Admin only. Sets any subset of the member's is_admin, is_billing and is_reviewer rights, and their
    per-member monthly cap in seconds. At least one field must be present. Demoting the workspace's last
    remaining admin is refused, evaluated inside the same atomic update so two concurrent demotions
    cannot both succeed and strand the workspace with no admin.

    Args:
        user_id (str):
        body (PatchOrgMemberBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | PatchOrgMemberResponse200]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    user_id: str,
    *,
    client: AuthenticatedClient,
    body: PatchOrgMemberBody,
) -> Error | PatchOrgMemberResponse200 | None:
    """Change a workspace member's rights or cap

     Admin only. Sets any subset of the member's is_admin, is_billing and is_reviewer rights, and their
    per-member monthly cap in seconds. At least one field must be present. Demoting the workspace's last
    remaining admin is refused, evaluated inside the same atomic update so two concurrent demotions
    cannot both succeed and strand the workspace with no admin.

    Args:
        user_id (str):
        body (PatchOrgMemberBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | PatchOrgMemberResponse200
    """

    return sync_detailed(
        user_id=user_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    user_id: str,
    *,
    client: AuthenticatedClient,
    body: PatchOrgMemberBody,
) -> Response[Error | PatchOrgMemberResponse200]:
    """Change a workspace member's rights or cap

     Admin only. Sets any subset of the member's is_admin, is_billing and is_reviewer rights, and their
    per-member monthly cap in seconds. At least one field must be present. Demoting the workspace's last
    remaining admin is refused, evaluated inside the same atomic update so two concurrent demotions
    cannot both succeed and strand the workspace with no admin.

    Args:
        user_id (str):
        body (PatchOrgMemberBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | PatchOrgMemberResponse200]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    user_id: str,
    *,
    client: AuthenticatedClient,
    body: PatchOrgMemberBody,
) -> Error | PatchOrgMemberResponse200 | None:
    """Change a workspace member's rights or cap

     Admin only. Sets any subset of the member's is_admin, is_billing and is_reviewer rights, and their
    per-member monthly cap in seconds. At least one field must be present. Demoting the workspace's last
    remaining admin is refused, evaluated inside the same atomic update so two concurrent demotions
    cannot both succeed and strand the workspace with no admin.

    Args:
        user_id (str):
        body (PatchOrgMemberBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | PatchOrgMemberResponse200
    """

    return (
        await asyncio_detailed(
            user_id=user_id,
            client=client,
            body=body,
        )
    ).parsed
