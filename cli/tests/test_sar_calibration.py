from core.sar_calibration import summarize

ROWS = [
    {"optical": 0.10, "sar_-14": 0.08, "iou_-14": 0.5, "sar_-16": 0.04, "iou_-16": 0.4},
    {"optical": 0.30, "sar_-14": 0.20, "iou_-14": 0.4, "sar_-16": 0.10, "iou_-16": 0.2},
]


def test_summarize_picks_best_mean_iou():
    summary, best = summarize(ROWS, [-14, -16])
    assert best == -14
    assert round(summary[-14]["mean_iou"], 3) == 0.45
    assert round(summary[-16]["mean_abs_error"], 3) == 0.13


def test_summarize_without_pairs():
    assert summarize([], [-14]) == ({}, None)
