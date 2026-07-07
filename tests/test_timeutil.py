"""Pyramid level routing and time parsing."""
from __future__ import annotations

import pytest

from qcm.timeutil import bucket_us, choose_level, parse_time

_LEVELS = ["100ms", "1s", "10s", "1min", "10min", "1h"]


def test_choose_level_short_window_goes_raw():
    # 1 s window / 2000 points → 0.5 ms per point: finer than every bucket.
    assert choose_level(1_000_000, 2000, _LEVELS) == "raw"


def test_choose_level_picks_coarsest_bucket_below_density():
    # 10 000 s over 2000 points → 5 s per point: 1s buckets fit, 10s do not.
    assert choose_level(10_000_000_000, 2000, _LEVELS) == "1s"


def test_choose_level_huge_window_tops_out():
    assert choose_level(10_000 * 3_600_000_000, 2000, _LEVELS) == "1h"


def test_choose_level_defaults_target_points():
    assert choose_level(10_000_000_000, 0, _LEVELS) == "1s"


def test_bucket_us_rejects_unknown_level():
    with pytest.raises(ValueError, match="Unknown pyramid level"):
        bucket_us("3s")


def test_parse_time_forms():
    assert parse_time(None, 7) == 7
    assert parse_time(12.7) == 12
    assert parse_time("123") == 123
    with pytest.raises(ValueError):
        parse_time(None)
