"""Точка входа: ``netspeed URL [-n 10] [--timeout 60]``."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence

from netspeed.measure import MEGABYTE, FetchError, Sample, fetch
from netspeed.stats import summarize

DEFAULT_REQUESTS = 10
DEFAULT_TIMEOUT = 60.0
EXIT_OK, EXIT_PARTIAL, EXIT_NO_DATA = 0, 1, 2


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="netspeed",
        description="Скачивает URL N раз подряд и печатает скорость скачивания.",
    )
    parser.add_argument("url", help="адрес тяжёлого файла, например картинки на 5-50 МБ")
    parser.add_argument(
        "-n",
        "--requests",
        type=int,
        default=DEFAULT_REQUESTS,
        help=f"число последовательных запросов (по умолчанию {DEFAULT_REQUESTS})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"предел на один запрос, с (по умолчанию {DEFAULT_TIMEOUT:g})",
    )
    args = parser.parse_args(argv)
    if args.requests < 1:
        parser.error("--requests должно быть >= 1")
    if not (math.isfinite(args.timeout) and args.timeout > 0):
        parser.error("--timeout должно быть положительным числом")
    if not args.url.startswith(("http://", "https://")):
        parser.error("нужен http:// или https:// адрес")
    return args


def _say(line: str = "") -> None:
    # stdout и stderr идут в одну консоль: без flush строки ошибок обгоняют
    # строки замеров, когда вывод перенаправлен в файл или pipe.
    print(line, flush=True)


def _complain(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    samples: list[Sample] = []
    failures = 0

    try:
        for i in range(1, args.requests + 1):
            prefix = f"[{i:>2}/{args.requests}]"
            try:
                sample = fetch(args.url, timeout=args.timeout)
            except FetchError as exc:
                failures += 1
                _complain(f"{prefix} ошибка: {exc}")
                continue
            samples.append(sample)
            _say(
                f"{prefix} {sample.body_bytes / MEGABYTE:8.2f} МБ  "
                f"{sample.seconds:7.3f} с  {sample.megabytes_per_second:8.2f} МБ/с"
            )
    except KeyboardInterrupt:
        _complain("Прервано — итог по уже скачанному.")

    if not samples:
        _complain("Ни одного успешного запроса — скорость не посчитать.")
        return EXIT_NO_DATA

    summary = summarize(samples)
    mbps = f"{summary.megabits_per_second:.1f} Мбит/с"
    _say()
    _say(f"Успешных запросов:  {summary.requests} из {args.requests}")
    _say(
        f"Скачано:            {summary.total_bytes / MEGABYTE:.2f} МБ ({summary.total_bytes} байт)"
    )
    _say(f"Среднее время:      {summary.mean_seconds:.3f} с")
    _say(f"Скорость:           {summary.megabytes_per_second:.2f} МБ/с ({mbps})")
    if summary.mean_bytes < MEGABYTE:
        _complain(
            "Внимание: файл меньше 1 МБ — время съедают DNS/TCP/TLS, "
            "скорость занижена. Возьмите файл потяжелее."
        )
    return EXIT_PARTIAL if failures or summary.requests < args.requests else EXIT_OK
