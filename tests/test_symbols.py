import pytest

from fcn_chart.symbols import InvalidSymbolError, normalize_symbol, split_symbols


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("TSM", "TSM"),
        (" nvda ", "NVDA"),
        ("BRK.B", "BRK-B"),
        ("6758", "6758.T"),
        ("130A", "130A.T"),
        ("6758.T", "6758.T"),
        ("6758.t", "6758.T"),
    ],
)
def test_normalize_symbol(raw, expected):
    assert normalize_symbol(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "12.T", "ABC$", "2330.TW"])
def test_normalize_symbol_rejects_invalid(raw):
    with pytest.raises(InvalidSymbolError):
        normalize_symbol(raw)


def test_split_symbols_handles_separators_and_dedup():
    assert split_symbols("TSM, NVDA，6758  tsm;AVGO") == ["TSM", "NVDA", "6758", "AVGO"]
