from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.buy_minutes_body import BuyMinutesBody
from ...models.error import Error
from ...models.purchase_response import PurchaseResponse
from ...types import Response


def _get_kwargs(
    *,
    body: BuyMinutesBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/billing/purchase",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | PurchaseResponse | None:
    if response.status_code == 200:
        response_200 = PurchaseResponse.from_dict(response.json())

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

    if response.status_code == 422:
        response_422 = Error.from_dict(response.json())

        return response_422

    if response.status_code == 429:
        response_429 = Error.from_dict(response.json())

        return response_429

    if response.status_code == 500:
        response_500 = Error.from_dict(response.json())

        return response_500

    if response.status_code == 502:
        response_502 = Error.from_dict(response.json())

        return response_502

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Error | PurchaseResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: BuyMinutesBody,
) -> Response[Error | PurchaseResponse]:
    """Charge the account's saved default card for a minute pack

     Charges a saved, fast_checkout_eligible payment method for one pack and credits the account's
    balance on success. quick_payment_method_id must be the account's current default, except when the
    account has no default at all, in which case naming an eligible card here makes it the new default.
    quick_payment_method_id is required: this API can only complete a purchase against a card already on
    file and has no way to open an interactive Checkout session, so an agent cannot use it to attach a
    new card. list_saved_cards can only list a card already on file, not create one; add a card first,
    either through the Hushscript app or by opening the hosted Checkout session create_setup_session
    returns. A request with no quick_payment_method_id, or a Quick Buy charge that needed
    authentication, a different payment method, or was declined, is refused outright rather than opened
    as a Checkout session nobody in this flow could complete. Needs the billing scope AND machine
    billing switched on for the account in the Hushscript app; either one off is a pat_scope_missing
    (code 2023) refusal, whichever it was.

    Args:
        body (BuyMinutesBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | PurchaseResponse]
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
    body: BuyMinutesBody,
) -> Error | PurchaseResponse | None:
    """Charge the account's saved default card for a minute pack

     Charges a saved, fast_checkout_eligible payment method for one pack and credits the account's
    balance on success. quick_payment_method_id must be the account's current default, except when the
    account has no default at all, in which case naming an eligible card here makes it the new default.
    quick_payment_method_id is required: this API can only complete a purchase against a card already on
    file and has no way to open an interactive Checkout session, so an agent cannot use it to attach a
    new card. list_saved_cards can only list a card already on file, not create one; add a card first,
    either through the Hushscript app or by opening the hosted Checkout session create_setup_session
    returns. A request with no quick_payment_method_id, or a Quick Buy charge that needed
    authentication, a different payment method, or was declined, is refused outright rather than opened
    as a Checkout session nobody in this flow could complete. Needs the billing scope AND machine
    billing switched on for the account in the Hushscript app; either one off is a pat_scope_missing
    (code 2023) refusal, whichever it was.

    Args:
        body (BuyMinutesBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | PurchaseResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: BuyMinutesBody,
) -> Response[Error | PurchaseResponse]:
    """Charge the account's saved default card for a minute pack

     Charges a saved, fast_checkout_eligible payment method for one pack and credits the account's
    balance on success. quick_payment_method_id must be the account's current default, except when the
    account has no default at all, in which case naming an eligible card here makes it the new default.
    quick_payment_method_id is required: this API can only complete a purchase against a card already on
    file and has no way to open an interactive Checkout session, so an agent cannot use it to attach a
    new card. list_saved_cards can only list a card already on file, not create one; add a card first,
    either through the Hushscript app or by opening the hosted Checkout session create_setup_session
    returns. A request with no quick_payment_method_id, or a Quick Buy charge that needed
    authentication, a different payment method, or was declined, is refused outright rather than opened
    as a Checkout session nobody in this flow could complete. Needs the billing scope AND machine
    billing switched on for the account in the Hushscript app; either one off is a pat_scope_missing
    (code 2023) refusal, whichever it was.

    Args:
        body (BuyMinutesBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | PurchaseResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: BuyMinutesBody,
) -> Error | PurchaseResponse | None:
    """Charge the account's saved default card for a minute pack

     Charges a saved, fast_checkout_eligible payment method for one pack and credits the account's
    balance on success. quick_payment_method_id must be the account's current default, except when the
    account has no default at all, in which case naming an eligible card here makes it the new default.
    quick_payment_method_id is required: this API can only complete a purchase against a card already on
    file and has no way to open an interactive Checkout session, so an agent cannot use it to attach a
    new card. list_saved_cards can only list a card already on file, not create one; add a card first,
    either through the Hushscript app or by opening the hosted Checkout session create_setup_session
    returns. A request with no quick_payment_method_id, or a Quick Buy charge that needed
    authentication, a different payment method, or was declined, is refused outright rather than opened
    as a Checkout session nobody in this flow could complete. Needs the billing scope AND machine
    billing switched on for the account in the Hushscript app; either one off is a pat_scope_missing
    (code 2023) refusal, whichever it was.

    Args:
        body (BuyMinutesBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | PurchaseResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
