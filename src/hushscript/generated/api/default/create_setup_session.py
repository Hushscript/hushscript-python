from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.create_setup_session_body import CreateSetupSessionBody
from ...models.error import Error
from ...models.setup_session_response import SetupSessionResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: CreateSetupSessionBody | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/billing/setup-session",
    }

    if not isinstance(body, Unset):
        _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | SetupSessionResponse | None:
    if response.status_code == 200:
        response_200 = SetupSessionResponse.from_dict(response.json())

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

    if response.status_code == 502:
        response_502 = Error.from_dict(response.json())

        return response_502

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Error | SetupSessionResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: CreateSetupSessionBody | Unset = UNSET,
) -> Response[Error | SetupSessionResponse]:
    """Open a hosted Checkout Session that saves a card with no charge

     Creates a Stripe Checkout Session in setup mode and returns its checkout_url. Open that URL in a
    browser you control (your own automation, not this API) so Stripe can render the card form and
    handle any bank authentication itself; card details never pass through this API. No charge is made.
    Once the caller completes the hosted page, the saved card becomes available from list_saved_cards
    and can be set as the default with set_default_card; list_saved_cards can lag a just-completed
    Session by up to 30 seconds, since nothing calls back into this API when the hosted page finishes,
    so retry rather than concluding the save failed. expires_at is when the Session stops accepting a
    card; call this endpoint again for a fresh link after that. idempotency_key is optional: omit it and
    every call opens a new Session, which is safe since a setup Session is never charged and expires on
    its own; supply your own key only if you want a retried call to land on the same Session instead.
    Needs the billing scope AND machine billing switched on for the account in the Hushscript app;
    either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Args:
        body (CreateSetupSessionBody | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | SetupSessionResponse]
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
    body: CreateSetupSessionBody | Unset = UNSET,
) -> Error | SetupSessionResponse | None:
    """Open a hosted Checkout Session that saves a card with no charge

     Creates a Stripe Checkout Session in setup mode and returns its checkout_url. Open that URL in a
    browser you control (your own automation, not this API) so Stripe can render the card form and
    handle any bank authentication itself; card details never pass through this API. No charge is made.
    Once the caller completes the hosted page, the saved card becomes available from list_saved_cards
    and can be set as the default with set_default_card; list_saved_cards can lag a just-completed
    Session by up to 30 seconds, since nothing calls back into this API when the hosted page finishes,
    so retry rather than concluding the save failed. expires_at is when the Session stops accepting a
    card; call this endpoint again for a fresh link after that. idempotency_key is optional: omit it and
    every call opens a new Session, which is safe since a setup Session is never charged and expires on
    its own; supply your own key only if you want a retried call to land on the same Session instead.
    Needs the billing scope AND machine billing switched on for the account in the Hushscript app;
    either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Args:
        body (CreateSetupSessionBody | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | SetupSessionResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: CreateSetupSessionBody | Unset = UNSET,
) -> Response[Error | SetupSessionResponse]:
    """Open a hosted Checkout Session that saves a card with no charge

     Creates a Stripe Checkout Session in setup mode and returns its checkout_url. Open that URL in a
    browser you control (your own automation, not this API) so Stripe can render the card form and
    handle any bank authentication itself; card details never pass through this API. No charge is made.
    Once the caller completes the hosted page, the saved card becomes available from list_saved_cards
    and can be set as the default with set_default_card; list_saved_cards can lag a just-completed
    Session by up to 30 seconds, since nothing calls back into this API when the hosted page finishes,
    so retry rather than concluding the save failed. expires_at is when the Session stops accepting a
    card; call this endpoint again for a fresh link after that. idempotency_key is optional: omit it and
    every call opens a new Session, which is safe since a setup Session is never charged and expires on
    its own; supply your own key only if you want a retried call to land on the same Session instead.
    Needs the billing scope AND machine billing switched on for the account in the Hushscript app;
    either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Args:
        body (CreateSetupSessionBody | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | SetupSessionResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: CreateSetupSessionBody | Unset = UNSET,
) -> Error | SetupSessionResponse | None:
    """Open a hosted Checkout Session that saves a card with no charge

     Creates a Stripe Checkout Session in setup mode and returns its checkout_url. Open that URL in a
    browser you control (your own automation, not this API) so Stripe can render the card form and
    handle any bank authentication itself; card details never pass through this API. No charge is made.
    Once the caller completes the hosted page, the saved card becomes available from list_saved_cards
    and can be set as the default with set_default_card; list_saved_cards can lag a just-completed
    Session by up to 30 seconds, since nothing calls back into this API when the hosted page finishes,
    so retry rather than concluding the save failed. expires_at is when the Session stops accepting a
    card; call this endpoint again for a fresh link after that. idempotency_key is optional: omit it and
    every call opens a new Session, which is safe since a setup Session is never charged and expires on
    its own; supply your own key only if you want a retried call to land on the same Session instead.
    Needs the billing scope AND machine billing switched on for the account in the Hushscript app;
    either one off is a pat_scope_missing (code 2023) refusal, whichever it was.

    Args:
        body (CreateSetupSessionBody | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | SetupSessionResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
