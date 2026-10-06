from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.set_default_card_body import SetDefaultCardBody
from ...models.set_default_card_response_200 import SetDefaultCardResponse200
from ...types import Response


def _get_kwargs(
    *,
    body: SetDefaultCardBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/billing/cards/default",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | SetDefaultCardResponse200 | None:
    if response.status_code == 200:
        response_200 = SetDefaultCardResponse200.from_dict(response.json())

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
) -> Response[Error | SetDefaultCardResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: SetDefaultCardBody,
) -> Response[Error | SetDefaultCardResponse200]:
    """Switch which saved card Quick Buy charges

     Sets the given payment method as the account's default, which is the card buy_minutes charges when a
    caller sends its id as quick_payment_method_id. Use this to switch the default or to pick among
    multiple eligible cards; buy_minutes only adopts one automatically when the account has no default
    at all. The id must belong to a payment method already on file, from list_saved_cards; a well formed
    id this account does not own answers not found, exactly like one that is not a payment method at
    all. Needs the billing scope AND machine billing switched on for the account in the Hushscript app;
    either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Args:
        body (SetDefaultCardBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | SetDefaultCardResponse200]
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
    body: SetDefaultCardBody,
) -> Error | SetDefaultCardResponse200 | None:
    """Switch which saved card Quick Buy charges

     Sets the given payment method as the account's default, which is the card buy_minutes charges when a
    caller sends its id as quick_payment_method_id. Use this to switch the default or to pick among
    multiple eligible cards; buy_minutes only adopts one automatically when the account has no default
    at all. The id must belong to a payment method already on file, from list_saved_cards; a well formed
    id this account does not own answers not found, exactly like one that is not a payment method at
    all. Needs the billing scope AND machine billing switched on for the account in the Hushscript app;
    either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Args:
        body (SetDefaultCardBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | SetDefaultCardResponse200
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: SetDefaultCardBody,
) -> Response[Error | SetDefaultCardResponse200]:
    """Switch which saved card Quick Buy charges

     Sets the given payment method as the account's default, which is the card buy_minutes charges when a
    caller sends its id as quick_payment_method_id. Use this to switch the default or to pick among
    multiple eligible cards; buy_minutes only adopts one automatically when the account has no default
    at all. The id must belong to a payment method already on file, from list_saved_cards; a well formed
    id this account does not own answers not found, exactly like one that is not a payment method at
    all. Needs the billing scope AND machine billing switched on for the account in the Hushscript app;
    either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Args:
        body (SetDefaultCardBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | SetDefaultCardResponse200]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: SetDefaultCardBody,
) -> Error | SetDefaultCardResponse200 | None:
    """Switch which saved card Quick Buy charges

     Sets the given payment method as the account's default, which is the card buy_minutes charges when a
    caller sends its id as quick_payment_method_id. Use this to switch the default or to pick among
    multiple eligible cards; buy_minutes only adopts one automatically when the account has no default
    at all. The id must belong to a payment method already on file, from list_saved_cards; a well formed
    id this account does not own answers not found, exactly like one that is not a payment method at
    all. Needs the billing scope AND machine billing switched on for the account in the Hushscript app;
    either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Args:
        body (SetDefaultCardBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | SetDefaultCardResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
