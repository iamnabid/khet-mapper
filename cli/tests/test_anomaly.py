from core.anomaly import anomaly_threshold, season_window
from core.validation import _shift


def test_short_window_is_padded_to_minimum():
    assert season_window(["2024-05-26", "2024-06-06"]) == ["2024-05-19", "2024-06-13"]


def test_long_window_is_unchanged():
    assert season_window(["2026-07-01", "2026-07-30"]) == ["2026-07-01", "2026-07-30"]


def test_threshold_is_mean_plus_three_sd_or_floor():
    assert anomaly_threshold([0.0, 0.0, 0.0]) == 0.02
    assert round(anomaly_threshold([0.02, 0.04, 0.06]), 3) == 0.1
    assert anomaly_threshold([0.05]) == 0.02


def test_shift_handles_leap_day():
    assert _shift("2024-02-29", years=-1) == "2023-02-28"
