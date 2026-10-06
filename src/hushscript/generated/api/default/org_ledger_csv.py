from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/ledger.csv",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | str | None:
    if response.status_code == 200:
        response_200 = response.text
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
) -> Response[Error | str]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[Error | str]:
    """Download the caller's organization's whole minute-pool ledger as CSV

     Downloads the caller's organization's entire org_credit_ledger history (not paged, unlike GET
    /v1/org/ledger) as a CSV file. Sets X-Hushscript-Csv-Truncated: 1 if the export hit its internal
    page ceiling.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | str]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> Error | str | None:
    """Download the caller's organization's whole minute-pool ledger as CSV

     Downloads the caller's organization's entire org_credit_ledger history (not paged, unlike GET
    /v1/org/ledger) as a CSV file. Sets X-Hushscript-Csv-Truncated: 1 if the export hit its internal
    page ceiling.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | str
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[Error | str]:
    """Download the caller's organization's whole minute-pool ledger as CSV

     Downloads the caller's organization's entire org_credit_ledger history (not paged, unlike GET
    /v1/org/ledger) as a CSV file. Sets X-Hushscript-Csv-Truncated: 1 if the export hit its internal
    page ceiling.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | str]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> Error | str | None:
    """Download the caller's organization's whole minute-pool ledger as CSV

     Downloads the caller's organization's entire org_credit_ledger history (not paged, unlike GET
    /v1/org/ledger) as a CSV file. Sets X-Hushscript-Csv-Truncated: 1 if the export hit its internal
    page ceiling.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | str
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
