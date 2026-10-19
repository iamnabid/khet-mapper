from core.flood_runs import longest_flagged_run, merge_observations


def test_no_flagged_observations():
    assert longest_flagged_run([("2024-07-01", 0.1), ("2024-07-10", 0.2)], 0.4) == 0


def test_single_flagged_observation_counts_one_day():
    assert longest_flagged_run([("2024-07-01", 0.5)], 0.4) == 1


def test_run_spans_consecutive_flagged_revisits():
    obs = [("2024-07-01", 0.5), ("2024-07-13", 0.6), ("2024-07-25", 0.45)]
    assert longest_flagged_run(obs, 0.4) == 25


def test_dry_observation_breaks_the_run():
    obs = [("2024-07-01", 0.5), ("2024-07-06", 0.1), ("2024-07-11", 0.5), ("2024-07-16", 0.5)]
    assert longest_flagged_run(obs, 0.4) == 6


def test_gap_longer_than_max_breaks_the_run():
    obs = [("2024-07-01", 0.5), ("2024-07-30", 0.5), ("2024-08-05", 0.5)]
    assert longest_flagged_run(obs, 0.4, max_gap_days=16) == 7


def test_unsorted_input_and_none_values():
    obs = [("2024-07-13", 0.6), ("2024-07-05", None), ("2024-07-01", 0.5)]
    assert longest_flagged_run(obs, 0.4) == 13


def test_higher_tier_fraction_gives_shorter_or_equal_run():
    obs = [("2024-07-01", 0.45), ("2024-07-13", 0.55), ("2024-07-25", 0.55)]
    assert longest_flagged_run(obs, 0.40) == 25
    assert longest_flagged_run(obs, 0.50) == 13


def test_merge_keeps_wetter_value_per_date_and_drops_none():
    optical = [("2024-07-01", 0.2), ("2024-07-06", None)]
    sar = [("2024-07-01", 0.7), ("2024-07-13", 0.5)]
    assert merge_observations(optical, sar) == [("2024-07-01", 0.7), ("2024-07-13", 0.5)]


def test_radar_fills_cloudy_gap_between_optical_passes():
    # Optical sees water on Jul 1 and Aug 10 only (monsoon cloud in between);
    # alone that's two separate 1-day runs. Radar passes bridge the gap.
    optical = [("2024-07-01", 0.6), ("2024-08-10", 0.6)]
    sar = [("2024-07-12", 0.5), ("2024-07-24", 0.5), ("2024-08-05", 0.5)]
    assert longest_flagged_run(optical, 0.4) == 1
    assert longest_flagged_run(merge_observations(optical, sar), 0.4) == 41
