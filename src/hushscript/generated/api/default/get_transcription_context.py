from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.transcription_context_response import TranscriptionContextResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/transcription-context",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | TranscriptionContextResponse | None:
    if response.status_code == 200:
        response_200 = TranscriptionContextResponse.from_dict(response.json())

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
) -> Response[Error | TranscriptionContextResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[Error | TranscriptionContextResponse]:
    """Read the account's saved transcription context

     Returns every saved dictionary and prompt preset on the account. A dictionary teaches the
    transcriber names and terms it would otherwise mishear; a prompt preset is standing free-text
    guidance. Both can be selected by id on an upload. This response is not paginated and carries no
    cursor: an account may hold at most 50 dictionaries and 20 prompt presets, both enforced when they
    are created, so a single response is always the complete set.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | TranscriptionContextResponse]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> Error | TranscriptionContextResponse | None:
    """Read the account's saved transcription context

     Returns every saved dictionary and prompt preset on the account. A dictionary teaches the
    transcriber names and terms it would otherwise mishear; a prompt preset is standing free-text
    guidance. Both can be selected by id on an upload. This response is not paginated and carries no
    cursor: an account may hold at most 50 dictionaries and 20 prompt presets, both enforced when they
    are created, so a single response is always the complete set.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | TranscriptionContextResponse
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[Error | TranscriptionContextResponse]:
    """Read the account's saved transcription context

     Returns every saved dictionary and prompt preset on the account. A dictionary teaches the
    transcriber names and terms it would otherwise mishear; a prompt preset is standing free-text
    guidance. Both can be selected by id on an upload. This response is not paginated and carries no
    cursor: an account may hold at most 50 dictionaries and 20 prompt presets, both enforced when they
    are created, so a single response is always the complete set.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | TranscriptionContextResponse]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> Error | TranscriptionContextResponse | None:
    """Read the account's saved transcription context

     Returns every saved dictionary and prompt preset on the account. A dictionary teaches the
    transcriber names and terms it would otherwise mishear; a prompt preset is standing free-text
    guidance. Both can be selected by id on an upload. This response is not paginated and carries no
    cursor: an account may hold at most 50 dictionaries and 20 prompt presets, both enforced when they
    are created, so a single response is always the complete set.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | TranscriptionContextResponse
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
