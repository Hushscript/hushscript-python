from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.account_response import AccountResponse
from ...models.error import Error
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/account",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AccountResponse | Error | None:
    if response.status_code == 200:
        response_200 = AccountResponse.from_dict(response.json())

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
) -> Response[AccountResponse | Error]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[AccountResponse | Error]:
    """Read the account's balance, expiry and upload admission limits

     Returns the caller's net credit balance, when that balance is next scheduled to expire without a
    completed transcription or purchase, whether a card is on file, the account's data region, and the
    account's current daily-minutes and concurrent-jobs limits. Call this before create_upload to
    confirm there is enough balance and daily headroom for the upload about to be attempted.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AccountResponse | Error]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> AccountResponse | Error | None:
    """Read the account's balance, expiry and upload admission limits

     Returns the caller's net credit balance, when that balance is next scheduled to expire without a
    completed transcription or purchase, whether a card is on file, the account's data region, and the
    account's current daily-minutes and concurrent-jobs limits. Call this before create_upload to
    confirm there is enough balance and daily headroom for the upload about to be attempted.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AccountResponse | Error
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[AccountResponse | Error]:
    """Read the account's balance, expiry and upload admission limits

     Returns the caller's net credit balance, when that balance is next scheduled to expire without a
    completed transcription or purchase, whether a card is on file, the account's data region, and the
    account's current daily-minutes and concurrent-jobs limits. Call this before create_upload to
    confirm there is enough balance and daily headroom for the upload about to be attempted.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AccountResponse | Error]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> AccountResponse | Error | None:
    """Read the account's balance, expiry and upload admission limits

     Returns the caller's net credit balance, when that balance is next scheduled to expire without a
    completed transcription or purchase, whether a card is on file, the account's data region, and the
    account's current daily-minutes and concurrent-jobs limits. Call this before create_upload to
    confirm there is enough balance and daily headroom for the upload about to be attempted.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AccountResponse | Error
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
