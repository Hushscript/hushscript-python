from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.deleted_transcripts_response import DeletedTranscriptsResponse
from ...models.error import Error
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
        "url": "/v1/transcripts/deleted",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> DeletedTranscriptsResponse | Error | None:
    if response.status_code == 200:
        response_200 = DeletedTranscriptsResponse.from_dict(response.json())

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
) -> Response[DeletedTranscriptsResponse | Error]:
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
) -> Response[DeletedTranscriptsResponse | Error]:
    """List deletion records for removed transcripts

     Returns a page of the deletion records kept after a transcript is removed, whichever path removed
    it: an explicit delete, a scheduled deletion, the retention sweep or account deletion. Each record
    carries the transcript's title, duration and upload time, when and why it was deleted, and the
    stored deletion receipt. The transcript content itself is gone and cannot be recovered. Records are
    ordered by the deleted transcript's original upload time, newest first, so they interleave with GET
    /v1/transcripts by the same key. Pass the next_cursor value from one page as the cursor parameter of
    the next request to page further back; the cursor is opaque and this API refuses one it did not
    mint, including a cursor minted by GET /v1/transcripts.

    Args:
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeletedTranscriptsResponse | Error]
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
) -> DeletedTranscriptsResponse | Error | None:
    """List deletion records for removed transcripts

     Returns a page of the deletion records kept after a transcript is removed, whichever path removed
    it: an explicit delete, a scheduled deletion, the retention sweep or account deletion. Each record
    carries the transcript's title, duration and upload time, when and why it was deleted, and the
    stored deletion receipt. The transcript content itself is gone and cannot be recovered. Records are
    ordered by the deleted transcript's original upload time, newest first, so they interleave with GET
    /v1/transcripts by the same key. Pass the next_cursor value from one page as the cursor parameter of
    the next request to page further back; the cursor is opaque and this API refuses one it did not
    mint, including a cursor minted by GET /v1/transcripts.

    Args:
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeletedTranscriptsResponse | Error
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
) -> Response[DeletedTranscriptsResponse | Error]:
    """List deletion records for removed transcripts

     Returns a page of the deletion records kept after a transcript is removed, whichever path removed
    it: an explicit delete, a scheduled deletion, the retention sweep or account deletion. Each record
    carries the transcript's title, duration and upload time, when and why it was deleted, and the
    stored deletion receipt. The transcript content itself is gone and cannot be recovered. Records are
    ordered by the deleted transcript's original upload time, newest first, so they interleave with GET
    /v1/transcripts by the same key. Pass the next_cursor value from one page as the cursor parameter of
    the next request to page further back; the cursor is opaque and this API refuses one it did not
    mint, including a cursor minted by GET /v1/transcripts.

    Args:
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeletedTranscriptsResponse | Error]
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
) -> DeletedTranscriptsResponse | Error | None:
    """List deletion records for removed transcripts

     Returns a page of the deletion records kept after a transcript is removed, whichever path removed
    it: an explicit delete, a scheduled deletion, the retention sweep or account deletion. Each record
    carries the transcript's title, duration and upload time, when and why it was deleted, and the
    stored deletion receipt. The transcript content itself is gone and cannot be recovered. Records are
    ordered by the deleted transcript's original upload time, newest first, so they interleave with GET
    /v1/transcripts by the same key. Pass the next_cursor value from one page as the cursor parameter of
    the next request to page further back; the cursor is opaque and this API refuses one it did not
    mint, including a cursor minted by GET /v1/transcripts.

    Args:
        cursor (str | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeletedTranscriptsResponse | Error
    """

    return (
        await asyncio_detailed(
            client=client,
            cursor=cursor,
            limit=limit,
        )
    ).parsed
