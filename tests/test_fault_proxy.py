from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest

from scripts._fault_proxy import (
    MAX_HEADER_BYTES,
    LoopbackConnectProxy,
    child_environment,
)


@pytest.fixture
def echo_target() -> Iterator[tuple[str, int]]:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(0.1)
    stopped = threading.Event()
    connections: list[socket.socket] = []
    workers: list[threading.Thread] = []

    def echo(connection: socket.socket) -> None:
        connection.settimeout(0.1)
        try:
            while not stopped.is_set():
                try:
                    chunk = connection.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    return
                connection.sendall(chunk)
        except OSError:
            return
        finally:
            connection.close()

    def accept() -> None:
        while not stopped.is_set():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            connections.append(connection)
            worker = threading.Thread(target=echo, args=(connection,), daemon=True)
            workers.append(worker)
            worker.start()

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    try:
        yield listener.getsockname()
    finally:
        stopped.set()
        listener.close()
        thread.join(timeout=1)
        for connection in connections:
            connection.close()
        for worker in workers:
            worker.join(timeout=1)
        assert not thread.is_alive() and all(not item.is_alive() for item in workers)


def connect_socket(proxy: LoopbackConnectProxy) -> socket.socket:
    address = urlsplit(proxy.url)
    assert address.hostname == "127.0.0.1" and address.port is not None
    return socket.create_connection((address.hostname, address.port), timeout=1)


def response(connection: socket.socket) -> tuple[bytes, bytes]:
    received = bytearray()
    while b"\r\n\r\n" not in received:
        try:
            chunk = connection.recv(4096)
        except (ConnectionResetError, ConnectionAbortedError):
            break
        if not chunk:
            break
        received.extend(chunk)
    header, _, tail = bytes(received).partition(b"\r\n\r\n")
    return header, tail


def tunnel(
    proxy: LoopbackConnectProxy, target: tuple[str, int], initial: bytes = b""
) -> tuple[socket.socket, bytes]:
    connection = connect_socket(proxy)
    connection.sendall(
        f"CONNECT {target[0]}:{target[1]} HTTP/1.1\r\nHost: ignored\r\n\r\n".encode()
        + initial
    )
    header, tail = response(connection)
    assert header == b"HTTP/1.1 200 Connection Established"
    return connection, tail


def receive_exact(
    connection: socket.socket, expected: int, initial: bytes = b""
) -> bytes:
    received = bytearray(initial)
    while len(received) < expected:
        chunk = connection.recv(expected - len(received))
        assert chunk
        received.extend(chunk)
    return bytes(received)


def test_tunnel_relays_both_directions_and_preserves_initial_bytes(
    echo_target: tuple[str, int],
) -> None:
    with LoopbackConnectProxy(local_targets={echo_target}) as proxy:
        payload = b"opaque TLS test bytes\x00\xff" * 1000
        client, tail = tunnel(proxy, echo_target, b"initial")
        with client:
            assert receive_exact(client, 7, tail) == b"initial"
            client.sendall(payload)
            client.shutdown(socket.SHUT_WR)
            assert receive_exact(client, len(payload)) == payload
        assert proxy.snapshot()["connect_requests"] == 1
    assert proxy.close() is True
    assert proxy.snapshot()["active_tunnels"] == 0


@pytest.mark.parametrize(
    "authority",
    [
        "facebook.com.evil.invalid:443",
        "evilfacebook.com:443",
        "facebook.com:444",
        "127.0.0.1:443",
        "[::1]:443",
        "user@facebook.com:443",
        "facebook.com:443/path",
        "facebook.com:+443",
        "facebook.com:0",
        "facebook.com:65536",
        "facebook.com:not-a-port",
        "facebook..com:443",
        "-host.facebook.com:443",
    ],
)
def test_rejected_authorities_never_open_outbound_socket(
    authority: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with LoopbackConnectProxy() as proxy:
        client = connect_socket(proxy)

        def forbidden(*args: object, **kwargs: object) -> None:
            raise AssertionError("Rejected authority attempted an outbound connection")

        monkeypatch.setattr(socket, "create_connection", forbidden)
        with client:
            client.sendall(f"CONNECT {authority} HTTP/1.1\r\n\r\n".encode())
            header, tail = response(client)
            assert header.startswith((b"HTTP/1.1 400", b"HTTP/1.1 403"))
            assert not tail
        assert proxy.snapshot()["rejected_connects"] == 1


@pytest.mark.parametrize(
    "host",
    [
        "facebook.com",
        "deep.gateway.facebook.com",
        "messenger.com",
        "cdn.fbcdn.net",
        "cdn.fbsbx.com",
        "mmg.whatsapp.net",
        "whatsapp.com",
    ],
)
def test_default_meta_allowlist_uses_only_hermetic_outbound_sockets(
    host: str,
    echo_target: tuple[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct_connect = socket.create_connection
    outbound = []

    def local_connect(address: tuple[str, int], timeout: float) -> socket.socket:
        if address[0] == "127.0.0.1":
            return direct_connect(address, timeout)
        assert address == (host, 443)
        outbound.append(address)
        return direct_connect(echo_target, timeout)

    monkeypatch.setattr(socket, "create_connection", local_connect)
    with LoopbackConnectProxy() as proxy:
        client, _ = tunnel(proxy, (host, 443))
        with client:
            client.sendall(b"opaque bytes")
            assert receive_exact(client, 12) == b"opaque bytes"
        assert outbound == [(host, 443)]


def test_connection_cap_keeps_existing_tunnel_usable(
    echo_target: tuple[str, int],
) -> None:
    with LoopbackConnectProxy(local_targets={echo_target}, max_connections=1) as proxy:
        client, _ = tunnel(proxy, echo_target)
        with client, connect_socket(proxy) as extra:
            try:
                extra.sendall(b"CONNECT facebook.com:443 HTTP/1.1\r\n\r\n")
            except (ConnectionResetError, ConnectionAbortedError):
                pass
            header, _ = response(extra)
            assert not header.startswith(b"HTTP/1.1 200")
            client.sendall(b"still connected")
            assert receive_exact(client, 15) == b"still connected"
        assert proxy.snapshot()["rejected_connects"] == 1


def test_non_connect_and_oversized_headers_never_echo_request() -> None:
    secret = b"private-header-do-not-echo"
    with LoopbackConnectProxy() as proxy:
        with connect_socket(proxy) as client:
            client.sendall(b"GET / HTTP/1.1\r\nX-Test: " + secret + b"\r\n\r\n")
            header, tail = response(client)
            assert header.startswith(b"HTTP/1.1 400")
            assert secret not in header + tail
        with connect_socket(proxy) as client:
            client.sendall(
                b"CONNECT facebook.com:443 HTTP/1.1\r\nX-Test: "
                + secret
                + b"x" * MAX_HEADER_BYTES
            )
            header, tail = response(client)
            assert not header.startswith(b"HTTP/1.1 200")
            assert len(header + tail) < 256 and secret not in header + tail
        assert proxy.snapshot()["rejected_connects"] == 2


def test_incomplete_header_has_total_deadline() -> None:
    with LoopbackConnectProxy(header_timeout=0.1) as proxy:
        with connect_socket(proxy) as client:
            client.sendall(b"CONNECT ")
            header, _ = response(client)
            assert header.startswith(b"HTTP/1.1 408")


def test_outage_cuts_only_owned_tunnels_and_expires_without_restore_call(
    echo_target: tuple[str, int],
) -> None:
    unrelated = socket.create_connection(echo_target, timeout=1)
    with unrelated, LoopbackConnectProxy(local_targets={echo_target}) as proxy:
        old_client, _ = tunnel(proxy, echo_target)
        with old_client:
            proxy.begin_outage(0.2)
            assert proxy.snapshot()["cut_tunnels"] == 1
            assert proxy.snapshot()["active_tunnels"] == 0
            try:
                assert old_client.recv(1) == b""
            except ConnectionResetError:
                pass
        with connect_socket(proxy) as rejected:
            rejected.sendall(
                f"CONNECT {echo_target[0]}:{echo_target[1]} HTTP/1.1\r\n\r\n".encode()
            )
            header, _ = response(rejected)
            assert header.startswith(b"HTTP/1.1 503")
        unrelated.sendall(b"outside proxy")
        assert receive_exact(unrelated, 13) == b"outside proxy"
        time.sleep(0.25)
        restored, _ = tunnel(proxy, echo_target)
        with restored:
            restored.sendall(b"restored")
            assert receive_exact(restored, 8) == b"restored"
        assert proxy.snapshot()["rejected_connects"] >= 1


def test_close_cancels_partial_headers_and_joins_workers() -> None:
    proxy = LoopbackConnectProxy(header_timeout=60, cleanup_timeout=1)
    with connect_socket(proxy) as client:
        client.sendall(b"CONNECT ")
        started = time.monotonic()
        assert proxy.close() is True
        assert time.monotonic() - started < 1.5
    assert proxy.close() is True
    with pytest.raises(RuntimeError, match="closed"):
        proxy.begin_outage(1)


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf"), 301])
def test_outage_rejects_unbounded_or_invalid_duration(seconds: float) -> None:
    with LoopbackConnectProxy() as proxy:
        with pytest.raises(ValueError):
            proxy.begin_outage(seconds)


def test_child_environment_changes_only_a_copy_and_clears_proxy_bypass() -> None:
    original = {
        "PATH": "unrelated-setting",
        "HTTPS_PROXY": "http://old.invalid",
        "HtTp_PrOxY": "http://mixed.invalid",
        "NO_PROXY": "facebook.com",
        "no_proxy": "*",
    }
    environment = child_environment("http://127.0.0.1:12345", original)
    assert original["NO_PROXY"] == "facebook.com"
    assert original["HTTPS_PROXY"] == "http://old.invalid"
    assert environment["PATH"] == "unrelated-setting"
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        assert environment[name] == "http://127.0.0.1:12345"
    assert environment["NO_PROXY"] == environment["no_proxy"] == ""
    assert "HtTp_PrOxY" not in environment


@pytest.mark.parametrize(
    "url",
    [
        "http://external.invalid:8080",
        "https://127.0.0.1:8080",
        "http://127.0.0.1",
        "http://user:secret@127.0.0.1:8080",
        "http://127.0.0.1:8080/path",
    ],
)
def test_child_environment_rejects_external_or_credential_proxy(url: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        child_environment(url, {})


def test_local_target_permission_must_be_exact_loopback() -> None:
    with pytest.raises(ValueError, match="loopback"):
        LoopbackConnectProxy(local_targets={("192.0.2.1", 443)})
