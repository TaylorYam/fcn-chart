import pytest

from fcn_chart.symbols import InvalidSymbolError, display_ticker, normalize_symbol


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


@pytest.mark.parametrize(
    ("yahoo", "expected"),
    [("MSFT", "MSFT"), ("BRK-B", "BRK.B"), ("6758.T", "6758 JT"), ("130A.T", "130A JT")],
)
def test_display_ticker(yahoo, expected):
    assert display_ticker(yahoo) == expected
