from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.job_list import JobList
from ...models.list_jobs_active import ListJobsActive
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    active: ListJobsActive | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_active: str | Unset = UNSET
    if not isinstance(active, Unset):
        json_active = active

    params["active"] = json_active

    params["cursor"] = cursor

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/jobs",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | JobList | None:
    if response.status_code == 200:
        response_200 = JobList.from_dict(response.json())

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
) -> Response[Error | JobList]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    active: ListJobsActive | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Response[Error | JobList]:
    """List the account's transcription jobs

     Returns a page of pipeline jobs for the caller's account, newest first. Jobs accumulate for the
    lifetime of the account, not just while in flight, so this list pages: pass the next_cursor value
    from one page as the cursor parameter of the next request to page forward; the cursor is opaque and
    this API refuses one it did not mint rather than silently restarting at page one, since a caller
    that trusted a silent restart would believe it had paged forward when it had not. Pass active=1 to
    see only jobs that have not yet reached a terminal state.

    Args:
        active (ListJobsActive | Unset):
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | JobList]
    """

    kwargs = _get_kwargs(
        active=active,
        cursor=cursor,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    active: ListJobsActive | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Error | JobList | None:
    """List the account's transcription jobs

     Returns a page of pipeline jobs for the caller's account, newest first. Jobs accumulate for the
    lifetime of the account, not just while in flight, so this list pages: pass the next_cursor value
    from one page as the cursor parameter of the next request to page forward; the cursor is opaque and
    this API refuses one it did not mint rather than silently restarting at page one, since a caller
    that trusted a silent restart would believe it had paged forward when it had not. Pass active=1 to
    see only jobs that have not yet reached a terminal state.

    Args:
        active (ListJobsActive | Unset):
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | JobList
    """

    return sync_detailed(
        client=client,
        active=active,
        cursor=cursor,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    active: ListJobsActive | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Response[Error | JobList]:
    """List the account's transcription jobs

     Returns a page of pipeline jobs for the caller's account, newest first. Jobs accumulate for the
    lifetime of the account, not just while in flight, so this list pages: pass the next_cursor value
    from one page as the cursor parameter of the next request to page forward; the cursor is opaque and
    this API refuses one it did not mint rather than silently restarting at page one, since a caller
    that trusted a silent restart would believe it had paged forward when it had not. Pass active=1 to
    see only jobs that have not yet reached a terminal state.

    Args:
        active (ListJobsActive | Unset):
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | JobList]
    """

    kwargs = _get_kwargs(
        active=active,
        cursor=cursor,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    active: ListJobsActive | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Error | JobList | None:
    """List the account's transcription jobs

     Returns a page of pipeline jobs for the caller's account, newest first. Jobs accumulate for the
    lifetime of the account, not just while in flight, so this list pages: pass the next_cursor value
    from one page as the cursor parameter of the next request to page forward; the cursor is opaque and
    this API refuses one it did not mint rather than silently restarting at page one, since a caller
    that trusted a silent restart would believe it had paged forward when it had not. Pass active=1 to
    see only jobs that have not yet reached a terminal state.

    Args:
        active (ListJobsActive | Unset):
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | JobList
    """

    return (
        await asyncio_detailed(
            client=client,
            active=active,
            cursor=cursor,
            limit=limit,
        )
    ).parsed
