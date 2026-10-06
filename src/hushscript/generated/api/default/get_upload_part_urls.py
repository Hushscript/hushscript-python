from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error import Error
from ...models.get_upload_part_urls_response_200_type_0 import (
    GetUploadPartUrlsResponse200Type0,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    job: str,
    *,
    start: int | Unset = 1,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["start"] = start

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/uploads/{job}/part-urls".format(
            job=quote(str(job), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Error | GetUploadPartUrlsResponse200Type0 | None | None:
    if response.status_code == 200:

        def _parse_response_200(
            data: object,
        ) -> GetUploadPartUrlsResponse200Type0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_200_type_0 = GetUploadPartUrlsResponse200Type0.from_dict(data)

                return response_200_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(GetUploadPartUrlsResponse200Type0 | None, data)

        response_200 = _parse_response_200(response.json())

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
) -> Response[Error | GetUploadPartUrlsResponse200Type0 | None]:
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
    start: int | Unset = 1,
) -> Response[Error | GetUploadPartUrlsResponse200Type0 | None]:
    """Fetch a page of presigned direct-to-R2 part URLs

     Returns a fresh page of presigned PUT URLs for the given job's direct-to-R2 upload, starting at the
    requested part number. Presigned URLs expire, so a client resuming a stalled transfer should call
    this again rather than reusing URLs from create_upload's response.

    Args:
        job (str):
        start (int | Unset):  Default: 1.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | GetUploadPartUrlsResponse200Type0 | None]
    """

    kwargs = _get_kwargs(
        job=job,
        start=start,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    job: str,
    *,
    client: AuthenticatedClient,
    start: int | Unset = 1,
) -> Error | GetUploadPartUrlsResponse200Type0 | None | None:
    """Fetch a page of presigned direct-to-R2 part URLs

     Returns a fresh page of presigned PUT URLs for the given job's direct-to-R2 upload, starting at the
    requested part number. Presigned URLs expire, so a client resuming a stalled transfer should call
    this again rather than reusing URLs from create_upload's response.

    Args:
        job (str):
        start (int | Unset):  Default: 1.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | GetUploadPartUrlsResponse200Type0 | None
    """

    return sync_detailed(
        job=job,
        client=client,
        start=start,
    ).parsed


async def asyncio_detailed(
    job: str,
    *,
    client: AuthenticatedClient,
    start: int | Unset = 1,
) -> Response[Error | GetUploadPartUrlsResponse200Type0 | None]:
    """Fetch a page of presigned direct-to-R2 part URLs

     Returns a fresh page of presigned PUT URLs for the given job's direct-to-R2 upload, starting at the
    requested part number. Presigned URLs expire, so a client resuming a stalled transfer should call
    this again rather than reusing URLs from create_upload's response.

    Args:
        job (str):
        start (int | Unset):  Default: 1.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Error | GetUploadPartUrlsResponse200Type0 | None]
    """

    kwargs = _get_kwargs(
        job=job,
        start=start,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    job: str,
    *,
    client: AuthenticatedClient,
    start: int | Unset = 1,
) -> Error | GetUploadPartUrlsResponse200Type0 | None | None:
    """Fetch a page of presigned direct-to-R2 part URLs

     Returns a fresh page of presigned PUT URLs for the given job's direct-to-R2 upload, starting at the
    requested part number. Presigned URLs expire, so a client resuming a stalled transfer should call
    this again rather than reusing URLs from create_upload's response.

    Args:
        job (str):
        start (int | Unset):  Default: 1.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Error | GetUploadPartUrlsResponse200Type0 | None
    """

    return (
        await asyncio_detailed(
            job=job,
            client=client,
            start=start,
        )
    ).parsed
