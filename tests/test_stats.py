from __future__ import annotations

import pytest

from netspeed.measure import Sample
from netspeed.stats import summarize


def test_speed_is_total_bytes_over_total_time_not_mean_of_speeds() -> None:
    # 10 МБ за 1 с (10 МБ/с) и 10 МБ за 9 с (~1.1 МБ/с).
    # Среднее скоростей дало бы ~5.6 МБ/с, реально прошло 20 МБ за 10 с = 2 МБ/с.
    s = summarize([Sample(10_000_000, 1.0), Sample(10_000_000, 9.0)])
    assert s.megabytes_per_second == pytest.approx(2.0)
    assert s.megabits_per_second == pytest.approx(16.0)


def test_mean_time_and_total_volume() -> None:
    s = summarize([Sample(1_000, 0.5), Sample(3_000, 1.5)])
    assert s.total_bytes == 4_000
    assert s.mean_seconds == pytest.approx(1.0)


def test_no_samples_is_an_error() -> None:
    with pytest.raises(ValueError):
        summarize([])
