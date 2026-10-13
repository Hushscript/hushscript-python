from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.org_usage_report_csv_group_by import (
    OrgUsageReportCsvGroupBy,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    from_: int,
    to: int,
    group_by: OrgUsageReportCsvGroupBy | Unset = "member",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["from"] = from_

    params["to"] = to

    json_group_by: str | Unset = UNSET
    if not isinstance(group_by, Unset):
        json_group_by = group_by

    params["group_by"] = json_group_by

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/usage.csv",
        "params": params,
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

    if response.status_code == 422:
        response_422 = Error.from_dict(response.json())

        return response_422

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
    from_: int,
    to: int,
    group_by: OrgUsageReportCsvGroupBy | Unset = "member",
) -> Response[Error | str]:
    """Download the caller's organization's settled spend by member, matter or client as CSV

     Same aggregation as GET /v1/org/usage, downloaded as a CSV file instead of a JSON body.

    Args:
        from_ (int):
        to (int):
        group_by (OrgUsageReportCsvGroupBy | Unset):  Default: 'member'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | str]
    """

    kwargs = _get_kwargs(
        from_=from_,
        to=to,
        group_by=group_by,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    from_: int,
    to: int,
    group_by: OrgUsageReportCsvGroupBy | Unset = "member",
) -> Error | str | None:
    """Download the caller's organization's settled spend by member, matter or client as CSV

     Same aggregation as GET /v1/org/usage, downloaded as a CSV file instead of a JSON body.

    Args:
        from_ (int):
        to (int):
        group_by (OrgUsageReportCsvGroupBy | Unset):  Default: 'member'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | str
    """

    return sync_detailed(
        client=client,
        from_=from_,
        to=to,
        group_by=group_by,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    from_: int,
    to: int,
    group_by: OrgUsageReportCsvGroupBy | Unset = "member",
) -> Response[Error | str]:
    """Download the caller's organization's settled spend by member, matter or client as CSV

     Same aggregation as GET /v1/org/usage, downloaded as a CSV file instead of a JSON body.

    Args:
        from_ (int):
        to (int):
        group_by (OrgUsageReportCsvGroupBy | Unset):  Default: 'member'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | str]
    """

    kwargs = _get_kwargs(
        from_=from_,
        to=to,
        group_by=group_by,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    from_: int,
    to: int,
    group_by: OrgUsageReportCsvGroupBy | Unset = "member",
) -> Error | str | None:
    """Download the caller's organization's settled spend by member, matter or client as CSV

     Same aggregation as GET /v1/org/usage, downloaded as a CSV file instead of a JSON body.

    Args:
        from_ (int):
        to (int):
        group_by (OrgUsageReportCsvGroupBy | Unset):  Default: 'member'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | str
    """

    return (
        await asyncio_detailed(
            client=client,
            from_=from_,
            to=to,
            group_by=group_by,
        )
    ).parsed
