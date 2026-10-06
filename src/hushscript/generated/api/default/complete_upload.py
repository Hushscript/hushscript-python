from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.complete_upload_body import CompleteUploadBody
from ...models.error import Error
from ...models.upload_complete_response import UploadCompleteResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    job: str,
    *,
    body: CompleteUploadBody | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/uploads/{job}/complete".format(
            job=quote(str(job), safe=""),
        ),
    }

    if not isinstance(body, Unset):
        _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | UploadCompleteResponse | None:
    if response.status_code == 200:
        response_200 = UploadCompleteResponse.from_dict(response.json())

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
) -> Response[Error | UploadCompleteResponse]:
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
    body: CompleteUploadBody | Unset = UNSET,
) -> Response[Error | UploadCompleteResponse]:
    """Finish an upload and start transcription

     Marks every declared part as uploaded, probes the assembled object's exact duration, and reconciles
    the credit hold to the verified billable seconds; if the balance cannot cover the verified total the
    job is rejected and the hold released rather than run over budget. On success the job moves to
    queued or processing (reported as queued while verification is still pending) for transcription.

    Args:
        job (str):
        body (CompleteUploadBody | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | UploadCompleteResponse]
    """

    kwargs = _get_kwargs(
        job=job,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    job: str,
    *,
    client: AuthenticatedClient,
    body: CompleteUploadBody | Unset = UNSET,
) -> Error | UploadCompleteResponse | None:
    """Finish an upload and start transcription

     Marks every declared part as uploaded, probes the assembled object's exact duration, and reconciles
    the credit hold to the verified billable seconds; if the balance cannot cover the verified total the
    job is rejected and the hold released rather than run over budget. On success the job moves to
    queued or processing (reported as queued while verification is still pending) for transcription.

    Args:
        job (str):
        body (CompleteUploadBody | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | UploadCompleteResponse
    """

    return sync_detailed(
        job=job,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    job: str,
    *,
    client: AuthenticatedClient,
    body: CompleteUploadBody | Unset = UNSET,
) -> Response[Error | UploadCompleteResponse]:
    """Finish an upload and start transcription

     Marks every declared part as uploaded, probes the assembled object's exact duration, and reconciles
    the credit hold to the verified billable seconds; if the balance cannot cover the verified total the
    job is rejected and the hold released rather than run over budget. On success the job moves to
    queued or processing (reported as queued while verification is still pending) for transcription.

    Args:
        job (str):
        body (CompleteUploadBody | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | UploadCompleteResponse]
    """

    kwargs = _get_kwargs(
        job=job,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    job: str,
    *,
    client: AuthenticatedClient,
    body: CompleteUploadBody | Unset = UNSET,
) -> Error | UploadCompleteResponse | None:
    """Finish an upload and start transcription

     Marks every declared part as uploaded, probes the assembled object's exact duration, and reconciles
    the credit hold to the verified billable seconds; if the balance cannot cover the verified total the
    job is rejected and the hold released rather than run over budget. On success the job moves to
    queued or processing (reported as queued while verification is still pending) for transcription.

    Args:
        job (str):
        body (CompleteUploadBody | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | UploadCompleteResponse
    """

    return (
        await asyncio_detailed(
            job=job,
            client=client,
            body=body,
        )
    ).parsed
