from __future__ import annotations

import pytest
from conftest import PAYLOAD, SLOW_BODY_CHUNKS, SLOW_BODY_DELAY, Server

from netspeed.measure import FetchError, fetch


def test_counts_every_body_byte(server: Server) -> None:
    sample = fetch(f"{server.base}/file", timeout=5)
    assert sample.body_bytes == len(PAYLOAD)


def test_time_includes_body_download_not_just_headers(server: Server) -> None:
    # Заголовки приходят мгновенно, тело — за ~0.5 с. Если засекать время до
    # заголовков (как response.elapsed в requests), скорость будет завышена в разы.
    sample = fetch(f"{server.base}/slow-body", timeout=5)
    assert sample.seconds >= SLOW_BODY_CHUNKS * SLOW_BODY_DELAY * 0.9


def test_asks_for_uncompressed_uncached_response(server: Server) -> None:
    fetch(f"{server.base}/file", timeout=5)
    headers = {k.lower(): v for k, v in server.recorder.headers[0].items()}
    assert headers["accept-encoding"] == "identity"
    assert headers["cache-control"] == "no-cache"


def test_truncated_body_is_failure_not_sample(server: Server) -> None:
    with pytest.raises(FetchError):
        fetch(f"{server.base}/truncated", timeout=5)


def test_http_error_is_failure(server: Server) -> None:
    with pytest.raises(FetchError, match="404"):
        fetch(f"{server.base}/missing", timeout=5)


def test_empty_body_is_failure(server: Server) -> None:
    with pytest.raises(FetchError, match="пустое"):
        fetch(f"{server.base}/empty", timeout=5)


def test_unreachable_host_is_failure() -> None:
    with pytest.raises(FetchError):
        fetch("http://127.0.0.1:9/", timeout=1)


def test_malformed_url_is_failure_not_crash() -> None:
    with pytest.raises(FetchError, match="некорректный адрес"):
        fetch("http://[::1/x", timeout=1)


def test_slow_body_over_deadline_is_failure(server: Server) -> None:
    # Каждый чанк приходит быстрее таймаута сокета, но весь ответ — нет.
    with pytest.raises(FetchError, match="не уложился"):
        fetch(f"{server.base}/slow-body", timeout=0.25)
