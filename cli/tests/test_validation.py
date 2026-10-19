from core.validation import detection


def test_no_during_passes_means_no_verdict():
    assert detection([0.01], []) == (None, None, None)


def test_floor_applies_when_pre_noise_is_tiny():
    detected, threshold, peak = detection([0.001, 0.002], [0.015])
    assert threshold == 0.02 and detected is False and peak == 0.015


def test_threshold_scales_with_pre_noise():
    detected, threshold, _ = detection([0.03], [0.08])
    assert round(threshold, 3) == 0.09 and detected is False
    assert detection([0.03], [0.12])[0] is True


def test_missing_pre_passes_uses_floor():
    assert detection([], [0.05])[:2] == (True, 0.02)


def test_baseline_is_stretched_to_minimum_length():
    from core.validation import with_baseline, control_window
    e = {"pre": ["2025-03-20", "2025-03-30"], "post": ["2025-04-11", "2025-04-30"]}
    assert with_baseline(e)["pre"] == ["2025-02-22", "2025-03-30"]
    assert with_baseline({"pre": ["2025-01-01", "2025-03-30"]})["pre"][0] == "2025-01-01"
    assert control_window(e) == ["2024-03-20", "2024-04-30"]


def test_year_earlier_shifts_all_windows():
    from core.validation import year_earlier
    e = {"id": "x", "pre": ["2024-08-07", "2024-09-12"], "during": ["2024-09-13", "2024-09-30"], "post": ["2024-10-01", "2024-10-20"]}
    c = year_earlier(e)
    assert c["pre"] == ["2023-08-07", "2023-09-12"] and c["during"][0] == "2023-09-13" and c["id"] == "x"
