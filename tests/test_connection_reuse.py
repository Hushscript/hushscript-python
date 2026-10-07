# pyright: reportPrivateUsage=false
"""R54 over a real socket: a request that must not go out twice (rotate, a mutation, an unkeyed
create) is sent exactly once when the pooled connection it rides on dies after the server has read
the whole body. The GET control shows the server would see a second send, so "once" is not vacuous.
"""

from __future__ import annotations

import socket
import struct
import threading
from typing import TYPE_CHECKING

import httpx
import pytest

from conftest import TOKEN
from helpers import FakeClock
from hushscript import AsyncHushscript, Hushscript, HushscriptError
from hushscript._client import _async_inner, _sync_inner

if TYPE_CHECKING:
    from collections.abc import Iterator

BODY = b'{"balance_seconds":0,"held_seconds":0}'
ANSWER = (
    b"HTTP/1.1 200 OK\r\ncontent-type: application/json\r\nconnection: keep-alive\r\n"
    b"content-length: " + str(len(BODY)).encode() + b"\r\n\r\n" + BODY
)


class Server:
    """Serves each connection's first request normally. The second request on a connection is read
    in full and then the connection is killed with a FIN or an RST, unanswered."""

    def __init__(self, kill: str) -> None:
        self.kill = kill
        self.arrivals: list[tuple[int, str, str]] = []
        self.lock = threading.Lock()
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.port: int = self.listener.getsockname()[1]
        self.stopping = False
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def count(self, method: str, path: str) -> int:
        return sum(1 for _, m, p in self.arrivals if (m, p) == (method, path))

    def connections_of(self, method: str, path: str) -> list[int]:
        return [c for c, m, p in self.arrivals if (m, p) == (method, path)]

    def _accept(self) -> None:
        number = 0
        while not self.stopping:
            try:
                connection, _ = self.listener.accept()
            except OSError:
                return
            number += 1
            threading.Thread(target=self._serve, args=(connection, number), daemon=True).start()

    def _read_request(self, connection: socket.socket) -> tuple[str, str] | None:
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            chunk = connection.recv(65536)
            if not chunk:
                return None
            buffer += chunk
        head, _, rest = buffer.partition(b"\r\n\r\n")
        lines = head.decode().split("\r\n")
        method, path, _ = lines[0].split(" ", 2)
        length = 0
        for line in lines[1:]:
            name, _, value = line.partition(":")
            if name.lower() == "content-length":
                length = int(value)
        while len(rest) < length:
            chunk = connection.recv(65536)
            if not chunk:
                return None
            rest += chunk
        return method, path

    def _serve(self, connection: socket.socket, number: int) -> None:
        served = 0
        try:
            while True:
                request = self._read_request(connection)
                if request is None:
                    return
                with self.lock:
                    self.arrivals.append((number, *request))
                served += 1
                if served == 1:
                    connection.sendall(ANSWER)
                    continue
                if self.kill == "rst":
                    connection.setsockopt(
                        socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
                    )
                else:
                    connection.shutdown(socket.SHUT_RDWR)
                return
        except OSError:
            return
        finally:
            connection.close()

    def close(self) -> None:
        self.stopping = True
        self.listener.close()


@pytest.fixture(params=["fin", "rst"])
def server(request: pytest.FixtureRequest) -> Iterator[Server]:
    running = Server(request.param)
    yield running
    running.close()


WARM = ("GET", "/v1/account")


def client(server: Server) -> Hushscript:
    return Hushscript(TOKEN, base_url=server.base_url, clock=FakeClock(), max_retries=3)


def raw_post(hs: Hushscript, path: str, body: dict[str, object]) -> None:
    hs.api.get_httpx_client().post(path, json=body)


MUTATIONS = {
    "rotate": ("POST", "/v1/agent/credentials/rotate"),
    "org mutation": ("POST", "/v1/orgs/org_1/members"),
    "unkeyed create": ("POST", "/v1/uploads"),
}


def body_for(path: str) -> dict[str, object]:
    return {"size_bytes": 1000, "duration_seconds": 60} if path == "/v1/uploads" else {}


def send(hs: Hushscript, name: str) -> None:
    if name == "rotate":
        hs.agent.rotate_token()
    else:
        _, path = MUTATIONS[name]
        raw_post(hs, path, body_for(path))


@pytest.mark.parametrize("name", list(MUTATIONS))
def test_a_mutation_on_a_connection_that_dies_after_the_body_is_sent_once(
    server: Server, name: str
) -> None:
    hs = client(server)
    hs.balance()  # warms the connection every later request would be pooled on
    method, path = MUTATIONS[name]
    with pytest.raises(HushscriptError):
        send(hs, name)
    assert server.count(*WARM) == 1
    assert server.count(method, path) == 1
    assert server.connections_of(method, path) == server.connections_of(*WARM)  # the warm one
    hs.close()


def test_a_get_on_such_a_connection_is_sent_again_which_the_server_can_see(server: Server) -> None:
    hs = client(server)
    hs.balance()
    assert hs.balance().seconds == 0  # the second request dies; the retry lands on a new one
    assert server.count(*WARM) == 3
    assert len(set(server.connections_of(*WARM))) == 2
    hs.close()


async def send_async(hs: AsyncHushscript, name: str) -> None:
    if name == "rotate":
        await hs.agent.rotate_token()
    else:
        _, path = MUTATIONS[name]
        await hs.api.get_async_httpx_client().post(path, json=body_for(path))


@pytest.mark.parametrize("name", list(MUTATIONS))
@pytest.mark.anyio
async def test_async_a_mutation_on_a_connection_that_dies_after_the_body_is_sent_once(
    server: Server, name: str
) -> None:
    hs = AsyncHushscript(TOKEN, base_url=server.base_url, clock=FakeClock(), max_retries=3)
    await hs.balance()
    method, path = MUTATIONS[name]
    with pytest.raises(HushscriptError):
        await send_async(hs, name)
    assert server.count(*WARM) == 1
    assert server.count(method, path) == 1
    assert server.connections_of(method, path) == server.connections_of(*WARM)
    await hs.aclose()


def test_the_api_transports_never_offer_http2() -> None:
    """R54 rests on HTTP/1.1: an HTTP/2 stream reset is retried inside httpcore, below the SDK's
    one-send rule. Turning h2 on must fail here, not in production."""
    for transport in (_sync_inner(), _async_inner()):
        assert isinstance(transport, httpx.HTTPTransport | httpx.AsyncHTTPTransport)
        pool = transport._pool
        assert pool._http1 is True
        assert pool._http2 is False
