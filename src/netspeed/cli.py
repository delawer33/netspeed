"""Точка входа: ``netspeed URL [-n 10] [--timeout 30]``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from netspeed.measure import FetchError, Sample, fetch
from netspeed.stats import MEGABYTE, summarize

DEFAULT_REQUESTS = 10
DEFAULT_TIMEOUT = 30.0


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
        help=f"таймаут сокета на запрос, с (по умолчанию {DEFAULT_TIMEOUT:g})",
    )
    args = parser.parse_args(argv)
    if args.requests < 1:
        parser.error("--requests должно быть >= 1")
    if not args.url.startswith(("http://", "https://")):
        parser.error("нужен http:// или https:// адрес")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    samples: list[Sample] = []
    failures = 0

    for i in range(1, args.requests + 1):
        prefix = f"[{i:>2}/{args.requests}]"
        try:
            sample = fetch(args.url, timeout=args.timeout)
        except FetchError as exc:
            failures += 1
            print(f"{prefix} ошибка: {exc}", file=sys.stderr)
            continue
        samples.append(sample)
        rate = sample.bytes / sample.seconds / MEGABYTE
        print(
            f"{prefix} {sample.bytes / MEGABYTE:8.2f} МБ  {sample.seconds:7.3f} с  {rate:8.2f} МБ/с"
        )

    if not samples:
        print("Ни одного успешного запроса — скорость не посчитать.", file=sys.stderr)
        return 2

    s = summarize(samples)
    print()
    print(f"Успешных запросов:  {s.requests} из {args.requests}")
    print(f"Скачано:            {s.total_bytes / MEGABYTE:.2f} МБ ({s.total_bytes} байт)")
    print(f"Среднее время:      {s.mean_seconds:.3f} с")
    mbps = f"{s.megabits_per_second:.1f} Мбит/с"
    print(f"Скорость:           {s.megabytes_per_second:.2f} МБ/с ({mbps})")
    if s.total_bytes / s.requests < MEGABYTE:
        print(
            "Внимание: файл меньше 1 МБ — время съедают DNS/TCP/TLS, "
            "скорость занижена. Возьмите файл потяжелее.",
            file=sys.stderr,
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
