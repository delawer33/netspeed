from __future__ import annotations

import subprocess
import sys

import pytest
from conftest import PAYLOAD, Server

from netspeed import cli
from netspeed.cli import main
from netspeed.measure import Sample


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


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_rejects_bad_timeout(value: str) -> None:
    with pytest.raises(SystemExit):
        main(["http://example.com/file", f"--timeout={value}"])


def test_ctrl_c_summarizes_what_was_downloaded(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = 0

    def fake_fetch(url: str, timeout: float) -> Sample:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise KeyboardInterrupt
        return Sample(body_bytes=2_000_000, seconds=1.0)

    monkeypatch.setattr(cli, "fetch", fake_fetch)
    assert main(["http://example.com/file"]) == 1
    out = capsys.readouterr().out
    assert "Успешных запросов:  2 из 10" in out
    assert "2.00 МБ/с" in out


def test_lines_keep_request_order_when_piped(server: Server) -> None:
    # stdout в pipe буферизуется, stderr — нет: без flush ошибки [2/4] и [4/4]
    # печатаются раньше успешных [1/4] и [3/4].
    result = subprocess.run(
        [sys.executable, "-m", "netspeed", f"{server.base}/flaky", "-n", "4"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    order = [line[:6] for line in result.stdout.splitlines() if line.startswith("[")]
    assert order == ["[ 1/4]", "[ 2/4]", "[ 3/4]", "[ 4/4]"]
