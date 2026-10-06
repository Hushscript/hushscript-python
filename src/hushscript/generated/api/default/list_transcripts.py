from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.transcript_list import TranscriptList
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["cursor"] = cursor

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/transcripts",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | TranscriptList | None:
    if response.status_code == 200:
        response_200 = TranscriptList.from_dict(response.json())

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
) -> Response[Error | TranscriptList]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Response[Error | TranscriptList]:
    """List the account's transcripts

     Returns a page of the caller's transcripts, newest first, with metadata only (no body text). Pass
    the next_cursor value from one page as the cursor parameter of the next request to page forward; the
    cursor is opaque and this API refuses one it did not mint rather than silently restarting at page
    one, since a caller that trusted a silent restart would believe it had paged forward when it had
    not.

    Args:
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | TranscriptList]
    """

    kwargs = _get_kwargs(
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
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Error | TranscriptList | None:
    """List the account's transcripts

     Returns a page of the caller's transcripts, newest first, with metadata only (no body text). Pass
    the next_cursor value from one page as the cursor parameter of the next request to page forward; the
    cursor is opaque and this API refuses one it did not mint rather than silently restarting at page
    one, since a caller that trusted a silent restart would believe it had paged forward when it had
    not.

    Args:
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | TranscriptList
    """

    return sync_detailed(
        client=client,
        cursor=cursor,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Response[Error | TranscriptList]:
    """List the account's transcripts

     Returns a page of the caller's transcripts, newest first, with metadata only (no body text). Pass
    the next_cursor value from one page as the cursor parameter of the next request to page forward; the
    cursor is opaque and this API refuses one it did not mint rather than silently restarting at page
    one, since a caller that trusted a silent restart would believe it had paged forward when it had
    not.

    Args:
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | TranscriptList]
    """

    kwargs = _get_kwargs(
        cursor=cursor,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    cursor: str | Unset = UNSET,
    limit: int | Unset = 50,
) -> Error | TranscriptList | None:
    """List the account's transcripts

     Returns a page of the caller's transcripts, newest first, with metadata only (no body text). Pass
    the next_cursor value from one page as the cursor parameter of the next request to page forward; the
    cursor is opaque and this API refuses one it did not mint rather than silently restarting at page
    one, since a caller that trusted a silent restart would believe it had paged forward when it had
    not.

    Args:
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | TranscriptList
    """

    return (
        await asyncio_detailed(
            client=client,
            cursor=cursor,
            limit=limit,
        )
    ).parsed
