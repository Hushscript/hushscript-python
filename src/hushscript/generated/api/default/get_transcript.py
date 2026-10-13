from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.transcript_detail import TranscriptDetail
from ...types import Response


def _get_kwargs(
    id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/transcripts/{id}".format(
            id=quote(str(id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | TranscriptDetail | None:
    if response.status_code == 200:
        response_200 = TranscriptDetail.from_dict(response.json())

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
) -> Response[Error | TranscriptDetail]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    id: str,
    *,
    client: AuthenticatedClient,
) -> Response[Error | TranscriptDetail]:
    """Read one transcript's metadata and full body

     Returns one transcript's metadata plus its full structured body (the original transcription and any
    translations, keyed by locale). This is the reference way to fetch a transcript body from this API;
    format conversion such as SRT, WebVTT or plain text is the caller's job. This route reads the body
    through the same loader the rest of the backend uses, including its legacy full-envelope path for a
    transcript stored before the chunked-body protocol existed, so a caller can rely on this route
    regardless of which storage path actually served a given transcript. The backend's own code calls
    this whole-body route a rolling-deploy fallback for older clients, alongside the newer manifest and
    chunk endpoints; that label describes the route itself, not the legacy storage path, and this
    remains the frozen /v1 way to fetch any transcript's body.

    Args:
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | TranscriptDetail]
    """

    kwargs = _get_kwargs(
        id=id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: str,
    *,
    client: AuthenticatedClient,
) -> Error | TranscriptDetail | None:
    """Read one transcript's metadata and full body

     Returns one transcript's metadata plus its full structured body (the original transcription and any
    translations, keyed by locale). This is the reference way to fetch a transcript body from this API;
    format conversion such as SRT, WebVTT or plain text is the caller's job. This route reads the body
    through the same loader the rest of the backend uses, including its legacy full-envelope path for a
    transcript stored before the chunked-body protocol existed, so a caller can rely on this route
    regardless of which storage path actually served a given transcript. The backend's own code calls
    this whole-body route a rolling-deploy fallback for older clients, alongside the newer manifest and
    chunk endpoints; that label describes the route itself, not the legacy storage path, and this
    remains the frozen /v1 way to fetch any transcript's body.

    Args:
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | TranscriptDetail
    """

    return sync_detailed(
        id=id,
        client=client,
    ).parsed


async def asyncio_detailed(
    id: str,
    *,
    client: AuthenticatedClient,
) -> Response[Error | TranscriptDetail]:
    """Read one transcript's metadata and full body

     Returns one transcript's metadata plus its full structured body (the original transcription and any
    translations, keyed by locale). This is the reference way to fetch a transcript body from this API;
    format conversion such as SRT, WebVTT or plain text is the caller's job. This route reads the body
    through the same loader the rest of the backend uses, including its legacy full-envelope path for a
    transcript stored before the chunked-body protocol existed, so a caller can rely on this route
    regardless of which storage path actually served a given transcript. The backend's own code calls
    this whole-body route a rolling-deploy fallback for older clients, alongside the newer manifest and
    chunk endpoints; that label describes the route itself, not the legacy storage path, and this
    remains the frozen /v1 way to fetch any transcript's body.

    Args:
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | TranscriptDetail]
    """

    kwargs = _get_kwargs(
        id=id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: str,
    *,
    client: AuthenticatedClient,
) -> Error | TranscriptDetail | None:
    """Read one transcript's metadata and full body

     Returns one transcript's metadata plus its full structured body (the original transcription and any
    translations, keyed by locale). This is the reference way to fetch a transcript body from this API;
    format conversion such as SRT, WebVTT or plain text is the caller's job. This route reads the body
    through the same loader the rest of the backend uses, including its legacy full-envelope path for a
    transcript stored before the chunked-body protocol existed, so a caller can rely on this route
    regardless of which storage path actually served a given transcript. The backend's own code calls
    this whole-body route a rolling-deploy fallback for older clients, alongside the newer manifest and
    chunk endpoints; that label describes the route itself, not the legacy storage path, and this
    remains the frozen /v1 way to fetch any transcript's body.

    Args:
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | TranscriptDetail
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
        )
    ).parsed
