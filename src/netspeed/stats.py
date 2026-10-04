"""Сводка по серии замеров."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from netspeed.measure import MEGABYTE, Sample


@dataclass(frozen=True)
class Summary:
    requests: int
    total_bytes: int
    total_seconds: float

    @property
    def mean_seconds(self) -> float:
        return self.total_seconds / self.requests

    @property
    def mean_bytes(self) -> float:
        return self.total_bytes / self.requests

    @property
    def megabytes_per_second(self) -> float:
        """Суммарный объём / суммарное время.

        Не среднее скоростей отдельных запросов: оно переоценивает быстрые
        запросы и не совпадает с тем, сколько данных реально прошло за секунду.
        """
        return self.total_bytes / self.total_seconds / MEGABYTE

    @property
    def megabits_per_second(self) -> float:
        return self.megabytes_per_second * 8


def summarize(samples: Sequence[Sample]) -> Summary:
    if not samples:
        raise ValueError("нет успешных замеров")
    return Summary(
        requests=len(samples),
        total_bytes=sum(x.body_bytes for x in samples),
        total_seconds=sum(x.seconds for x in samples),
    )
