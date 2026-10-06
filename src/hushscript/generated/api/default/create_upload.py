from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.create_upload_body import CreateUploadBody
from ...models.error import Error
from ...models.upload_create_response import UploadCreateResponse
from ...types import Response


def _get_kwargs(
    *,
    body: CreateUploadBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/uploads",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | UploadCreateResponse | None:
    if response.status_code == 200:
        response_200 = UploadCreateResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = Error.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = Error.from_dict(response.json())

        return response_401

    if response.status_code == 402:
        response_402 = Error.from_dict(response.json())

        return response_402

    if response.status_code == 403:
        response_403 = Error.from_dict(response.json())

        return response_403

    if response.status_code == 409:
        response_409 = Error.from_dict(response.json())

        return response_409

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
) -> Response[Error | UploadCreateResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: CreateUploadBody,
) -> Response[Error | UploadCreateResponse]:
    """Start a new transcription upload and place a credit hold

     Declares the size and duration of a new audio upload, places a credit hold for the billable seconds
    (duration plus any transcription_options surcharge), and returns a job id plus, when direct-to-R2
    uploads are available, a first page of presigned part URLs. Resending the same idempotency_key
    returns the already-created job instead of opening a second one. Long direct-to-R2 transfers must
    call heartbeat_upload periodically or the job is reaped as idle.

    Args:
        body (CreateUploadBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | UploadCreateResponse]
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
    body: CreateUploadBody,
) -> Error | UploadCreateResponse | None:
    """Start a new transcription upload and place a credit hold

     Declares the size and duration of a new audio upload, places a credit hold for the billable seconds
    (duration plus any transcription_options surcharge), and returns a job id plus, when direct-to-R2
    uploads are available, a first page of presigned part URLs. Resending the same idempotency_key
    returns the already-created job instead of opening a second one. Long direct-to-R2 transfers must
    call heartbeat_upload periodically or the job is reaped as idle.

    Args:
        body (CreateUploadBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | UploadCreateResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: CreateUploadBody,
) -> Response[Error | UploadCreateResponse]:
    """Start a new transcription upload and place a credit hold

     Declares the size and duration of a new audio upload, places a credit hold for the billable seconds
    (duration plus any transcription_options surcharge), and returns a job id plus, when direct-to-R2
    uploads are available, a first page of presigned part URLs. Resending the same idempotency_key
    returns the already-created job instead of opening a second one. Long direct-to-R2 transfers must
    call heartbeat_upload periodically or the job is reaped as idle.

    Args:
        body (CreateUploadBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | UploadCreateResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: CreateUploadBody,
) -> Error | UploadCreateResponse | None:
    """Start a new transcription upload and place a credit hold

     Declares the size and duration of a new audio upload, places a credit hold for the billable seconds
    (duration plus any transcription_options surcharge), and returns a job id plus, when direct-to-R2
    uploads are available, a first page of presigned part URLs. Resending the same idempotency_key
    returns the already-created job instead of opening a second one. Long direct-to-R2 transfers must
    call heartbeat_upload periodically or the job is reaped as idle.

    Args:
        body (CreateUploadBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | UploadCreateResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
