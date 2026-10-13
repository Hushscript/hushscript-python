from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.heartbeat_upload_response_200 import HeartbeatUploadResponse200
from ...types import Response


def _get_kwargs(
    job: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/uploads/{job}/heartbeat".format(
            job=quote(str(job), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | HeartbeatUploadResponse200 | None:
    if response.status_code == 200:
        response_200 = HeartbeatUploadResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = Error.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = Error.from_dict(response.json())

        return response_403

    if response.status_code == 409:
        response_409 = Error.from_dict(response.json())

        return response_409

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
) -> Response[Error | HeartbeatUploadResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    job: str,
    *,
    client: AuthenticatedClient,
) -> Response[Error | HeartbeatUploadResponse200]:
    """Keep a direct-to-R2 upload alive

     Refreshes the job's activity clock for a direct-to-R2 transfer, whose bytes never pass through this
    API and so never otherwise refresh it. Call this at an interval well under the 20 minute idle
    timeout for the whole duration of a long transfer, or the job is reaped mid-flight.

    Args:
        job (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | HeartbeatUploadResponse200]
    """

    kwargs = _get_kwargs(
        job=job,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    job: str,
    *,
    client: AuthenticatedClient,
) -> Error | HeartbeatUploadResponse200 | None:
    """Keep a direct-to-R2 upload alive

     Refreshes the job's activity clock for a direct-to-R2 transfer, whose bytes never pass through this
    API and so never otherwise refresh it. Call this at an interval well under the 20 minute idle
    timeout for the whole duration of a long transfer, or the job is reaped mid-flight.

    Args:
        job (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | HeartbeatUploadResponse200
    """

    return sync_detailed(
        job=job,
        client=client,
    ).parsed


async def asyncio_detailed(
    job: str,
    *,
    client: AuthenticatedClient,
) -> Response[Error | HeartbeatUploadResponse200]:
    """Keep a direct-to-R2 upload alive

     Refreshes the job's activity clock for a direct-to-R2 transfer, whose bytes never pass through this
    API and so never otherwise refresh it. Call this at an interval well under the 20 minute idle
    timeout for the whole duration of a long transfer, or the job is reaped mid-flight.

    Args:
        job (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | HeartbeatUploadResponse200]
    """

    kwargs = _get_kwargs(
        job=job,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    job: str,
    *,
    client: AuthenticatedClient,
) -> Error | HeartbeatUploadResponse200 | None:
    """Keep a direct-to-R2 upload alive

     Refreshes the job's activity clock for a direct-to-R2 transfer, whose bytes never pass through this
    API and so never otherwise refresh it. Call this at an interval well under the 20 minute idle
    timeout for the whole duration of a long transfer, or the job is reaped mid-flight.

    Args:
        job (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | HeartbeatUploadResponse200
    """

    return (
        await asyncio_detailed(
            job=job,
            client=client,
        )
    ).parsed
