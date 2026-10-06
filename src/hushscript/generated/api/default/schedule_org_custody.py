from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.schedule_org_custody_body import ScheduleOrgCustodyBody
from ...models.schedule_org_custody_response_200 import ScheduleOrgCustodyResponse200
from ...types import Response


def _get_kwargs(
    *,
    body: ScheduleOrgCustodyBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/org/custody",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | ScheduleOrgCustodyResponse200 | None:
    if response.status_code == 200:
        response_200 = ScheduleOrgCustodyResponse200.from_dict(response.json())

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
) -> Response[Error | ScheduleOrgCustodyResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: ScheduleOrgCustodyBody,
) -> Response[Error | ScheduleOrgCustodyResponse200]:
    """Schedule the private to firm custody switch

     Org admin only. Schedules the workspace's custody mode to switch from private to firm a fixed notice
    period from now, and mails every member. Nothing changes immediately: a daily background lane flips
    the mode once the notice period expires. Only the value firm is accepted; a switch from firm back to
    private is not supported here, since transcripts already stamped under firm custody would silently
    change custodian.

    Args:
        body (ScheduleOrgCustodyBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | ScheduleOrgCustodyResponse200]
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
    client: AuthenticatedClient,
    body: ScheduleOrgCustodyBody,
) -> Error | ScheduleOrgCustodyResponse200 | None:
    """Schedule the private to firm custody switch

     Org admin only. Schedules the workspace's custody mode to switch from private to firm a fixed notice
    period from now, and mails every member. Nothing changes immediately: a daily background lane flips
    the mode once the notice period expires. Only the value firm is accepted; a switch from firm back to
    private is not supported here, since transcripts already stamped under firm custody would silently
    change custodian.

    Args:
        body (ScheduleOrgCustodyBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | ScheduleOrgCustodyResponse200
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: ScheduleOrgCustodyBody,
) -> Response[Error | ScheduleOrgCustodyResponse200]:
    """Schedule the private to firm custody switch

     Org admin only. Schedules the workspace's custody mode to switch from private to firm a fixed notice
    period from now, and mails every member. Nothing changes immediately: a daily background lane flips
    the mode once the notice period expires. Only the value firm is accepted; a switch from firm back to
    private is not supported here, since transcripts already stamped under firm custody would silently
    change custodian.

    Args:
        body (ScheduleOrgCustodyBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | ScheduleOrgCustodyResponse200]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: ScheduleOrgCustodyBody,
) -> Error | ScheduleOrgCustodyResponse200 | None:
    """Schedule the private to firm custody switch

     Org admin only. Schedules the workspace's custody mode to switch from private to firm a fixed notice
    period from now, and mails every member. Nothing changes immediately: a daily background lane flips
    the mode once the notice period expires. Only the value firm is accepted; a switch from firm back to
    private is not supported here, since transcripts already stamped under firm custody would silently
    change custodian.

    Args:
        body (ScheduleOrgCustodyBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | ScheduleOrgCustodyResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
