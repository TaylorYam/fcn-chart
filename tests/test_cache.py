import pytest

from fcn_chart import data


@pytest.fixture
def fake(monkeypatch):
    calls = []
    clock = {"now": 1000.0}

    def fake_fetch(symbol):
        calls.append(symbol)
        return f"history-{symbol}-{len(calls)}"

    monkeypatch.setattr(data, "fetch_history", fake_fetch)
    monkeypatch.setattr(data.clock, "monotonic", lambda: clock["now"])
    data.clear_cache()
    yield calls, clock
    data.clear_cache()


def test_repeated_symbol_within_ttl_uses_cache(fake):
    calls, _ = fake
    assert data.get_history("TSM") == data.get_history("TSM")
    assert calls == ["TSM"]


def test_different_symbols_are_cached_separately(fake):
    calls, _ = fake
    data.get_history("TSM")
    data.get_history("6758.T")
    assert calls == ["TSM", "6758.T"]


def test_expired_entry_is_refetched(fake):
    calls, clock = fake
    first = data.get_history("TSM")
    clock["now"] += data.CACHE_TTL_SECONDS
    assert data.get_history("TSM") != first
    assert calls == ["TSM", "TSM"]


def test_errors_are_not_cached(fake, monkeypatch):
    calls, _ = fake

    def failing(symbol):
        calls.append(symbol)
        raise data.SymbolNotFoundError(symbol)

    monkeypatch.setattr(data, "fetch_history", failing)
    for _ in range(2):
        with pytest.raises(data.SymbolNotFoundError):
            data.get_history("ZZZZ")
    assert calls == ["ZZZZ", "ZZZZ"]
