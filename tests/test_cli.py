from __future__ import annotations

import pytest
from conftest import PAYLOAD, Server

from netspeed.cli import main


def test_runs_ten_sequential_requests_by_default(server: Server) -> None:
    assert main([f"{server.base}/file"]) == 0
    assert len(server.recorder.headers) == 10
    assert server.recorder.max_in_flight == 1


def test_prints_mean_time_volume_and_speed(
    server: Server, capsys: pytest.CaptureFixture[str]
) -> None:
    main([f"{server.base}/file", "-n", "3"])
    out = capsys.readouterr().out
    assert f"({3 * len(PAYLOAD)} байт)" in out
    assert "Среднее время:" in out
    assert "МБ/с" in out


def test_partial_failure_reports_successes_and_exits_1(
    server: Server, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([f"{server.base}/flaky", "-n", "4"]) == 1
    captured = capsys.readouterr()
    assert "Успешных запросов:  2 из 4" in captured.out
    assert captured.err.count("HTTP 503") == 2


def test_truncated_bodies_never_count_as_samples(server: Server) -> None:
    assert main([f"{server.base}/truncated", "-n", "2"]) == 2


def test_all_failed_exits_2(server: Server, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([f"{server.base}/missing", "-n", "2"]) == 2
    assert "HTTP 404" in capsys.readouterr().err


def test_rejects_non_http_url() -> None:
    with pytest.raises(SystemExit):
        main(["ftp://example.com/file"])
