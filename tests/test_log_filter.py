"""The httpx request log never shows a signed part URL while a part PUT is out (spec 10, R47)."""

from __future__ import annotations

import logging

import httpx
import pytest

from hushscript._log import RequestLog, hiding_signed_url

SIGNED = (
    "https://acct.r2.example.com/bucket/job_1/part-3?X-Amz-Signature=deadbeef&X-Amz-Expires=3600"
)
OTHER = "https://api.example.com/v1/jobs?limit=5"
LABEL = "r2:part/3"


@pytest.fixture(autouse=True)
def _filter_installed() -> None:
    RequestLog("off")


def _text(caplog: pytest.LogCaptureFixture) -> str:
    return "\n".join(record.getMessage() for record in caplog.records)


def test_a_url_argument_is_swapped_for_the_label(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("httpx")
    with caplog.at_level(logging.INFO, logger="httpx"), hiding_signed_url(LABEL):
        logger.info('HTTP Request: %s %s "%s"', "PUT", httpx.URL(SIGNED), "HTTP/1.1 200 OK")
    assert _text(caplog) == f'HTTP Request: PUT {LABEL} "HTTP/1.1 200 OK"'


def test_a_url_already_formatted_into_the_message_goes_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("httpx")
    with caplog.at_level(logging.INFO, logger="httpx"), hiding_signed_url(LABEL):
        logger.info(f"HTTP Request: PUT {SIGNED} 200 and {OTHER}")  # noqa: G004  # the case
    text = _text(caplog)
    assert "deadbeef" not in text
    assert "X-Amz" not in text
    assert text == f"HTTP Request: PUT {LABEL} 200 and {OTHER}"


def test_a_url_in_a_mapping_argument_goes_too(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("httpx")
    with caplog.at_level(logging.INFO, logger="httpx"), hiding_signed_url(LABEL):
        logger.info("sent %(url)s and %(other)s", {"url": SIGNED, "other": OTHER})
    assert _text(caplog) == f"sent {LABEL} and {OTHER}"


def test_a_url_inside_a_longer_string_argument_goes_too(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("httpx")
    with caplog.at_level(logging.INFO, logger="httpx"), hiding_signed_url(LABEL):
        logger.info("%s", f"retrying {SIGNED} soon")
    assert "deadbeef" not in _text(caplog)


@pytest.mark.parametrize("key", ["sig", "signature", "X-Amz-Credential", "token", "Expires"])
def test_every_signing_query_key_counts(caplog: pytest.LogCaptureFixture, key: str) -> None:
    logger = logging.getLogger("httpx")
    with caplog.at_level(logging.INFO, logger="httpx"), hiding_signed_url(LABEL):
        logger.info(f"PUT https://r2.example.com/x?a=1&{key}=secret")  # noqa: G004  # the case
    assert _text(caplog) == f"PUT {LABEL}"


def test_nothing_changes_while_no_signed_request_is_out(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("httpx")
    with caplog.at_level(logging.INFO, logger="httpx"):
        logger.info("HTTP Request: %s %s", "GET", httpx.URL(OTHER))
        logger.info(f"seen {SIGNED}")  # noqa: G004  # the case
    assert _text(caplog) == f"HTTP Request: GET {OTHER}\nseen {SIGNED}"


def test_a_record_that_is_not_a_string_is_left_alone(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("httpx")
    with caplog.at_level(logging.INFO, logger="httpx"), hiding_signed_url(LABEL):
        logger.info(ValueError("odd"))
    assert _text(caplog) == "odd"
