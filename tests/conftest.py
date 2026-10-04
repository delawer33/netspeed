"""Локальный HTTP-сервер с маршрутами под каждый сценарий."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PAYLOAD = b"x" * 200_000
SLOW_BODY_CHUNKS = 5
SLOW_BODY_DELAY = 0.1


@dataclass
class Recorder:
    headers: list[dict[str, str]] = field(default_factory=list)
    in_flight: int = 0
    max_in_flight: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


class Handler(BaseHTTPRequestHandler):
    recorder: Recorder

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        rec = self.recorder
        with rec.lock:
            rec.headers.append(dict(self.headers.items()))
            rec.in_flight += 1
            rec.max_in_flight = max(rec.max_in_flight, rec.in_flight)
        try:
            self._route()
        finally:
            with rec.lock:
                rec.in_flight -= 1

    def _route(self) -> None:
        if self.path == "/file":
            time.sleep(0.01)  # чтобы параллельные запросы успели пересечься
            self._send(PAYLOAD)
        elif self.path == "/slow-body":
            # Заголовки уходят сразу, тело — по частям с паузами.
            chunk = b"y" * 10_000
            self.send_response(200)
            self.send_header("Content-Length", str(len(chunk) * SLOW_BODY_CHUNKS))
            self.end_headers()
            self.wfile.flush()
            for _ in range(SLOW_BODY_CHUNKS):
                time.sleep(SLOW_BODY_DELAY)
                self.wfile.write(chunk)
                self.wfile.flush()
        elif self.path == "/truncated":
            self.send_response(200)
            self.send_header("Content-Length", "1000")
            self.end_headers()
            self.wfile.write(b"z" * 500)
            self.wfile.flush()
            self.close_connection = True
        elif self.path == "/flaky":
            # Каждый второй запрос падает.
            if len(self.recorder.headers) % 2:
                self._send(PAYLOAD)
            else:
                self.send_error(503)
        elif self.path == "/empty":
            self._send(b"")
        else:
            self.send_error(404)

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@dataclass
class Server:
    base: str
    recorder: Recorder


@pytest.fixture
def server() -> Iterator[Server]:
    recorder = Recorder()
    handler = type("BoundHandler", (Handler,), {"recorder": recorder})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield Server(base=f"http://127.0.0.1:{httpd.server_port}", recorder=recorder)
    finally:
        httpd.shutdown()
        httpd.server_close()
