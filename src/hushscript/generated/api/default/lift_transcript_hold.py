from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.lift_transcript_hold_response_200 import LiftTranscriptHoldResponse200
from ...types import Response


def _get_kwargs(
    id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/v1/org/transcripts/{id}/hold".format(
            id=quote(str(id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | LiftTranscriptHoldResponse200 | None:
    if response.status_code == 200:
        response_200 = LiftTranscriptHoldResponse200.from_dict(response.json())

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
) -> Response[Error | LiftTranscriptHoldResponse200]:
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
) -> Response[Error | LiftTranscriptHoldResponse200]:
    """Lift a legal hold on a transcript

     Reviewer only. Lifts a legal hold on one transcript in the caller's firm-custody workspace. A held
    transcript is exempt from the retention sweep, the retention re-clamp sweep and ordinary deletion,
    and its body, translations, cleaned text and AI outputs cannot be edited or regenerated (409
    transcript_legal_hold), until the hold is lifted.

    Args:
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | LiftTranscriptHoldResponse200]
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
) -> Error | LiftTranscriptHoldResponse200 | None:
    """Lift a legal hold on a transcript

     Reviewer only. Lifts a legal hold on one transcript in the caller's firm-custody workspace. A held
    transcript is exempt from the retention sweep, the retention re-clamp sweep and ordinary deletion,
    and its body, translations, cleaned text and AI outputs cannot be edited or regenerated (409
    transcript_legal_hold), until the hold is lifted.

    Args:
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | LiftTranscriptHoldResponse200
    """

    return sync_detailed(
        id=id,
        client=client,
    ).parsed


async def asyncio_detailed(
    id: str,
    *,
    client: AuthenticatedClient,
) -> Response[Error | LiftTranscriptHoldResponse200]:
    """Lift a legal hold on a transcript

     Reviewer only. Lifts a legal hold on one transcript in the caller's firm-custody workspace. A held
    transcript is exempt from the retention sweep, the retention re-clamp sweep and ordinary deletion,
    and its body, translations, cleaned text and AI outputs cannot be edited or regenerated (409
    transcript_legal_hold), until the hold is lifted.

    Args:
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | LiftTranscriptHoldResponse200]
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
) -> Error | LiftTranscriptHoldResponse200 | None:
    """Lift a legal hold on a transcript

     Reviewer only. Lifts a legal hold on one transcript in the caller's firm-custody workspace. A held
    transcript is exempt from the retention sweep, the retention re-clamp sweep and ordinary deletion,
    and its body, translations, cleaned text and AI outputs cannot be edited or regenerated (409
    transcript_legal_hold), until the hold is lifted.

    Args:
        id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | LiftTranscriptHoldResponse200
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
        )
    ).parsed
