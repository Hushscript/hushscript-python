# pyright: reportPrivateUsage=false
"""The httpx request log never shows a signed part URL while a part PUT is out (spec 10, R47)."""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from hushscript._log import _SIGNED_URL_FILTER, RequestLog, hiding_signed_url

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


HTTPCORE_LOGGERS = [
    "httpcore",
    "httpcore.connection",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
    "httpcore.socks",
]


@pytest.mark.parametrize("name", HTTPCORE_LOGGERS)
def test_every_httpcore_logger_is_filtered_too(caplog: pytest.LogCaptureFixture, name: str) -> None:
    logger = logging.getLogger(name)
    with caplog.at_level(logging.DEBUG, logger=name), hiding_signed_url(LABEL):
        logger.debug(f"send_request_headers.started url={SIGNED!r} request=<Request [b'PUT']>")  # noqa: G004  # the case
    text = _text(caplog)
    assert "deadbeef" not in text
    assert LABEL in text


@pytest.mark.parametrize(
    "argument",
    [
        httpx.Request("PUT", SIGNED),
        httpx.URL(SIGNED),
        [SIGNED],
        {"url": SIGNED},
        (SIGNED, 1),
        b"PUT " + SIGNED.encode(),
    ],
    ids=["request", "url", "list", "dict", "tuple", "bytes"],
)
def test_an_argument_that_is_an_object_holding_the_url_is_hidden_too(
    caplog: pytest.LogCaptureFixture, argument: object
) -> None:
    logger = logging.getLogger("httpx")
    with caplog.at_level(logging.INFO, logger="httpx"), hiding_signed_url(LABEL):
        logger.info("sent %s", argument)
    text = _text(caplog)
    assert "deadbeef" not in text
    assert "X-Amz" not in text


def test_an_argument_with_no_signed_url_is_left_alone(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("httpx")
    other = httpx.Request("GET", OTHER)
    with caplog.at_level(logging.INFO, logger="httpx"), hiding_signed_url(LABEL):
        logger.info("%s %d %s", other, 5, None)
    assert _text(caplog) == f"{other} 5 None"


def test_an_argument_whose_text_fails_does_not_break_the_log_call() -> None:
    class Hostile:
        def __str__(self) -> str:
            raise RuntimeError("no text")

        def __repr__(self) -> str:
            raise RuntimeError("no text")

    logger = logging.getLogger("httpx")
    record = logger.makeRecord("httpx", logging.INFO, __file__, 1, "x %s", (Hostile(),), None)
    with hiding_signed_url(LABEL):
        assert _SIGNED_URL_FILTER.filter(record)


class _Ok(BaseHTTPRequestHandler):
    def do_PUT(self) -> None:  # the http.server hook
        self.rfile.read(int(self.headers.get("content-length", "0")))
        self.send_response(200)
        self.send_header("etag", '"abc"')
        self.send_header("content-length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Quiet."""


def test_a_real_part_put_with_httpx_and_httpcore_logging_never_shows_the_signature(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Ok)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/part-3?X-Amz-Signature=deadbeef&X-Amz-Expires=3600"
        with (
            caplog.at_level(logging.DEBUG, logger="httpx"),
            caplog.at_level(logging.DEBUG, logger="httpcore"),
            httpx.Client() as client,
            hiding_signed_url(LABEL),
        ):
            response = client.put(url, content=b"abc")
        assert response.status_code == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    text = _text(caplog)
    assert any(record.name.startswith("httpcore") for record in caplog.records)
    assert f"HTTP Request: PUT {LABEL}" in text
    assert "deadbeef" not in text
    assert "X-Amz" not in text
