from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.packs_response import PacksResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/billing/packs",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | PacksResponse | None:
    if response.status_code == 200:
        response_200 = PacksResponse.from_dict(response.json())

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
) -> Response[Error | PacksResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[Error | PacksResponse]:
    """List purchasable minute packs

     Returns the account's minute-pack catalogue, priced in the account's own currency, including any
    referral buyer bonus currently available. Read the id of the pack to buy from here before calling
    buy_minutes. Needs the billing scope AND machine billing switched on for the account in the
    Hushscript app; either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | PacksResponse]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> Error | PacksResponse | None:
    """List purchasable minute packs

     Returns the account's minute-pack catalogue, priced in the account's own currency, including any
    referral buyer bonus currently available. Read the id of the pack to buy from here before calling
    buy_minutes. Needs the billing scope AND machine billing switched on for the account in the
    Hushscript app; either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | PacksResponse
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[Error | PacksResponse]:
    """List purchasable minute packs

     Returns the account's minute-pack catalogue, priced in the account's own currency, including any
    referral buyer bonus currently available. Read the id of the pack to buy from here before calling
    buy_minutes. Needs the billing scope AND machine billing switched on for the account in the
    Hushscript app; either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | PacksResponse]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> Error | PacksResponse | None:
    """List purchasable minute packs

     Returns the account's minute-pack catalogue, priced in the account's own currency, including any
    referral buyer bonus currently available. Read the id of the pack to buy from here before calling
    buy_minutes. Needs the billing scope AND machine billing switched on for the account in the
    Hushscript app; either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | PacksResponse
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
