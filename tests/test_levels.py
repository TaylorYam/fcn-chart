import pytest

from fcn_chart.levels import compute_levels, round_half_up


def test_compute_levels_usd_two_decimals():
    levels = compute_levels(472.78, {"KO": 100, "K1": 80, "KI": 70}, "USD")
    assert [(lv.name, lv.label, lv.pct, lv.price) for lv in levels] == [
        ("KO", "KO", 100, 472.78),
        ("K1", "K", 80, 378.22),
        ("KI", "KI", 70, 330.95),
    ]


def test_compute_levels_jpy_whole_yen():
    levels = compute_levels(3753.0, {"KO": 100, "K1": 80, "KI": 70}, "JPY")
    assert [lv.price for lv in levels] == [3753, 3002, 2627]


def test_two_strikes_keep_k1_k2_labels():
    levels = compute_levels(490.30, {"KO": 100, "K1": 80, "K2": 75, "KI": 60}, "USD")
    assert [(lv.label, lv.price) for lv in levels] == [
        ("KO", 490.30),
        ("K1", 392.24),
        ("K2", 367.73),
        ("KI", 294.18),
    ]


def test_single_k2_is_labelled_k():
    levels = compute_levels(100.0, {"K2": 75}, "USD")
    assert [(lv.name, lv.label) for lv in levels] == [("K2", "K")]


def test_blank_pct_skips_line():
    levels = compute_levels(100.0, {"KO": 105, "K1": None, "KI": 65}, "USD")
    assert [lv.name for lv in levels] == ["KO", "KI"]


def test_non_positive_input_rejected():
    with pytest.raises(ValueError):
        compute_levels(0, {"KO": 100}, "USD")
    with pytest.raises(ValueError):
        compute_levels(100.0, {"KO": 0}, "USD")


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [(2.675, 2, 2.68), (0.125, 2, 0.13), (2626.5, 0, 2627), (330.946, 2, 330.95)],
)
def test_round_half_up(value, decimals, expected):
    assert round_half_up(value, decimals) == expected
