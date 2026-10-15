"""Bounded, test-only CONNECT faults without changing the machine network."""

from __future__ import annotations

import ipaddress
import math
import select
import socket
import sys
import threading
import time
from collections.abc import Collection, Mapping
from types import TracebackType
from urllib.parse import urlsplit

MAX_HEADER_BYTES = 8 * 1024
MAX_RELAY_BUFFER = 64 * 1024
META_DOMAINS = (
    "facebook.com",
    "messenger.com",
    "fbcdn.net",
    "fbsbx.com",
    "whatsapp.net",
    "whatsapp.com",
)


def child_environment(proxy_url: str, base_env: Mapping[str, str]) -> dict[str, str]:
    """Copy environment settings for one child, routing HTTPS through loopback."""
    try:
        parsed = urlsplit(proxy_url)
        valid = (
            parsed.scheme == "http"
            and parsed.hostname is not None
            and ipaddress.ip_address(parsed.hostname).is_loopback
            and parsed.port is not None
            and 0 < parsed.port <= 65535
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Fault proxy must use an HTTP loopback URL.")
    result = {
        key: value
        for key, value in base_env.items()
        if key.lower() not in {"http_proxy", "https_proxy", "no_proxy"}
    }
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        result[name] = proxy_url
    result["NO_PROXY"] = result["no_proxy"] = ""
    return result


def _authority(value: str) -> tuple[str, int]:
    if not value.isascii() or any(char in value for char in "@/?#\\ \t\r\n\x00"):
        raise ValueError("Invalid CONNECT authority.")
    host, separator, port_text = value.rpartition(":")
    if not separator or not port_text.isdecimal() or not host:
        raise ValueError("Invalid CONNECT authority.")
    port = int(port_text)
    if not 0 < port <= 65535:
        raise ValueError("Invalid CONNECT port.")
    if host.startswith("[") and host.endswith("]"):
        host = str(ipaddress.IPv6Address(host[1:-1]))
    else:
        host = host.lower().removesuffix(".")
        if len(host) > 253 or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or any(
                char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in label
            )
            for label in host.split(".")
        ):
            raise ValueError("Invalid CONNECT hostname.")
    return host, port


def _close_socket(connection: socket.socket) -> None:
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        connection.close()
    except OSError:
        pass


class LoopbackConnectProxy:
    """An opaque TLS tunnel with an automatically expiring outage gate.

    Only this instance's accepted sockets are ever closed. Explicit local_targets
    are for hermetic tests; by default only Meta DNS names on port 443 are allowed.
    No request header, target, credential, or relayed byte is retained in stats.
    """

    def __init__(
        self,
        *,
        local_targets: Collection[tuple[str, int]] = (),
        header_timeout: float = 5.0,
        connect_timeout: float = 3.0,
        cleanup_timeout: float = 5.0,
        max_connections: int = 64,
    ) -> None:
        for duration in (header_timeout, connect_timeout, cleanup_timeout):
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("Proxy timeouts must be positive and finite.")
        if type(max_connections) is not int or not 1 <= max_connections <= 256:
            raise ValueError("Proxy connection limit must be between 1 and 256.")
        self._local_targets: set[tuple[str, int]] = set()
        for host, port in local_targets:
            address = ipaddress.ip_address(host)
            if (
                not address.is_loopback
                or type(port) is not int
                or not 0 < port <= 65535
            ):
                raise ValueError(
                    "Test targets must be exact loopback addresses and ports."
                )
            self._local_targets.add((str(address), port))
        self._header_timeout = header_timeout
        self._connect_timeout = connect_timeout
        self._cleanup_timeout = cleanup_timeout
        self._max_connections = max_connections
        self._lock = threading.Lock()
        self._closed = False
        self._blocked_until = 0.0
        self._clients: set[socket.socket] = set()
        self._tunnels: set[tuple[socket.socket, socket.socket]] = set()
        self._workers: set[threading.Thread] = set()
        self._stats = {
            "connect_requests": 0,
            "cut_tunnels": 0,
            "rejected_connects": 0,
        }
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == "win32":
                self._listener.setsockopt(
                    socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1
                )
            self._listener.bind(("127.0.0.1", 0))
            self._listener.listen(max_connections)
            self._listener.settimeout(0.2)
            self.url = f"http://127.0.0.1:{self._listener.getsockname()[1]}"
            self._accept_thread = threading.Thread(
                target=self._accept, name="fault-proxy-accept", daemon=True
            )
            self._accept_thread.start()
        except BaseException:
            self._listener.close()
            raise

    def __enter__(self) -> LoopbackConnectProxy:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {**self._stats, "active_tunnels": len(self._tunnels)}

    def begin_outage(self, seconds: float) -> None:
        if not math.isfinite(seconds) or not 0 < seconds <= 300:
            raise ValueError("Outage must last between 0 and 300 finite seconds.")
        with self._lock:
            if self._closed:
                raise RuntimeError("Fault proxy is closed.")
            self._blocked_until = time.monotonic() + seconds
            tunnels = list(self._tunnels)
            self._tunnels.clear()
            self._stats["cut_tunnels"] += len(tunnels)
        for client, upstream in tunnels:
            _close_socket(client)
            _close_socket(upstream)

    def close(self) -> bool:
        """Close owned sockets and return whether all workers joined in time."""
        with self._lock:
            self._closed = True
            self._blocked_until = 0.0
            clients = list(self._clients)
            tunnels = list(self._tunnels)
            self._tunnels.clear()
        self._listener.close()
        for client in clients:
            _close_socket(client)
        for _, upstream in tunnels:
            _close_socket(upstream)
        deadline = time.monotonic() + self._cleanup_timeout
        self._accept_thread.join(max(0.0, deadline - time.monotonic()))
        while True:
            with self._lock:
                workers = list(self._workers)
            if not workers:
                return not self._accept_thread.is_alive()
            for worker in workers:
                worker.join(max(0.0, deadline - time.monotonic()))
            if time.monotonic() >= deadline:
                with self._lock:
                    return not self._workers and not self._accept_thread.is_alive()

    def _accept(self) -> None:
        while True:
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                if self._closed or len(self._workers) >= self._max_connections:
                    self._stats["rejected_connects"] += 1
                    _close_socket(connection)
                    continue
                self._clients.add(connection)
                worker = threading.Thread(
                    target=self._handle,
                    args=(connection,),
                    name="fault-proxy-tunnel",
                    daemon=True,
                )
                self._workers.add(worker)
                try:
                    worker.start()
                except RuntimeError:
                    self._workers.discard(worker)
                    self._clients.discard(connection)
                    _close_socket(connection)

    def _reject(self, client: socket.socket, status: str) -> None:
        with self._lock:
            self._stats["rejected_connects"] += 1
        try:
            client.settimeout(0.2)
            client.sendall(
                f"HTTP/1.1 {status}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode(
                    "ascii"
                )
            )
        except OSError:
            pass

    def _request(self, client: socket.socket) -> tuple[str, bytes] | None:
        data = bytearray()
        deadline = time.monotonic() + self._header_timeout
        while True:
            boundary = data.find(b"\r\n\r\n")
            if boundary >= 0:
                header, remaining = bytes(data[:boundary]), bytes(data[boundary + 4 :])
                try:
                    method, authority, version = header.split(b"\r\n", 1)[0].split(b" ")
                    if method != b"CONNECT" or version not in {
                        b"HTTP/1.0",
                        b"HTTP/1.1",
                    }:
                        raise ValueError("Unsupported HTTP request.")
                    value = authority.decode("ascii")
                except (ValueError, UnicodeDecodeError):
                    self._reject(client, "400 Bad Request")
                    return None
                with self._lock:
                    self._stats["connect_requests"] += 1
                return value, remaining
            if len(data) >= MAX_HEADER_BYTES:
                self._reject(client, "431 Request Header Fields Too Large")
                return None
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                self._reject(client, "408 Request Timeout")
                return None
            client.settimeout(remaining_seconds)
            try:
                chunk = client.recv(min(4096, MAX_HEADER_BYTES - len(data)))
            except socket.timeout:
                self._reject(client, "408 Request Timeout")
                return None
            if not chunk:
                return None
            data.extend(chunk)

    def _permitted(self, host: str, port: int) -> bool:
        if (host, port) in self._local_targets:
            return True
        return port == 443 and any(
            host == domain or host.endswith("." + domain) for domain in META_DOMAINS
        )

    def _handle(self, client: socket.socket) -> None:
        upstream: socket.socket | None = None
        established = False
        try:
            request = self._request(client)
            if request is None:
                return
            authority, initial = request
            try:
                host, port = _authority(authority)
            except ValueError:
                self._reject(client, "400 Bad Request")
                return
            if not self._permitted(host, port):
                self._reject(client, "403 Forbidden")
                return
            with self._lock:
                blocked = self._closed or time.monotonic() < self._blocked_until
            if blocked:
                self._reject(client, "503 Service Unavailable")
                return
            # Direct sockets deliberately ignore environment proxy settings.
            upstream = socket.create_connection((host, port), self._connect_timeout)
            with self._lock:
                blocked = self._closed or time.monotonic() < self._blocked_until
                if not blocked:
                    self._tunnels.add((client, upstream))
            if blocked:
                self._reject(client, "503 Service Unavailable")
                return
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            established = True
            self._relay(client, upstream, initial)
        except OSError:
            # Never insert an HTTP error into an established opaque tunnel.
            if not established:
                self._reject(client, "502 Bad Gateway")
        finally:
            _close_socket(client)
            if upstream is not None:
                _close_socket(upstream)
            with self._lock:
                self._clients.discard(client)
                if upstream is not None:
                    self._tunnels.discard((client, upstream))
                self._workers.discard(threading.current_thread())

    def _relay(
        self, client: socket.socket, upstream: socket.socket, initial: bytes
    ) -> None:
        destinations = {client: upstream, upstream: client}
        buffers = {client: bytearray(), upstream: bytearray(initial)}
        readers = set(destinations)
        shutdown_writes: set[socket.socket] = set()
        for connection in destinations:
            connection.setblocking(False)
        while readers or any(buffers.values()):
            with self._lock:
                if self._closed or (client, upstream) not in self._tunnels:
                    return
            readable = [
                source
                for source in readers
                if len(buffers[destinations[source]]) < MAX_RELAY_BUFFER
            ]
            writable = [target for target, pending in buffers.items() if pending]
            try:
                ready_read, ready_write, _ = select.select(readable, writable, (), 0.2)
            except (OSError, ValueError):
                return
            for source in ready_read:
                target = destinations[source]
                try:
                    chunk = source.recv(
                        min(4096, MAX_RELAY_BUFFER - len(buffers[target]))
                    )
                except BlockingIOError:
                    continue
                if chunk:
                    buffers[target].extend(chunk)
                else:
                    readers.discard(source)
            for target in ready_write:
                try:
                    sent = target.send(buffers[target])
                except BlockingIOError:
                    continue
                if sent <= 0:
                    return
                del buffers[target][:sent]
            for source, target in destinations.items():
                if (
                    source not in readers
                    and not buffers[target]
                    and target not in shutdown_writes
                ):
                    target.shutdown(socket.SHUT_WR)
                    shutdown_writes.add(target)
