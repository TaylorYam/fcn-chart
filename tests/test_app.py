import pytest
from fastapi.testclient import TestClient

from fcn_chart import app as app_module
from fcn_chart import data
from fcn_chart.data import Candle, PriceHistory


@pytest.fixture
def client(monkeypatch):
    calls = []

    def fake_fetch(symbol):
        calls.append(symbol)
        if symbol == "ZZZZ":
            raise data.SymbolNotFoundError("查無資料：ZZZZ")
        return PriceHistory(
            symbol=symbol,
            name="Sony Group Corporation",
            exchange="TSE",
            currency="JPY",
            timezone="Asia/Tokyo",
            candles=[
                Candle("2026-10-01", 3700, 3760, 3690, 3720, 1_200_000),
                Candle("2026-10-02", 3722, 3770, 3710, 3753, 1_500_000),
            ],
        )

    monkeypatch.setattr(app_module.data, "fetch_history", fake_fetch)
    data.clear_cache()
    test_client = TestClient(app_module.app)
    test_client.calls = calls
    return test_client


def test_chart_returns_levels_from_last_close(client):
    res = client.get("/api/chart", params={"symbol": "6758", "ko": 100, "k1": 80, "ki": 70})
    assert res.status_code == 200
    body = res.json()
    assert client.calls == ["6758.T"]
    assert body["ref_date"] == "2026-10-02"
    assert body["ref_close"] == 3753
    assert body["decimals"] == 0
    assert body["ticker"] == "6758 JT"
    assert [(lv["name"], lv["label"], lv["price"]) for lv in body["levels"]] == [
        ("KO", "KO", 3753),
        ("K1", "K", 3002),
        ("KI", "KI", 2627),
    ]
    assert body["exchange"] == "TSE"
    assert body["candles"][-1]["volume"] == 1_500_000


def test_chart_two_strikes(client):
    params = {"symbol": "6758", "ko": 100, "k1": 80, "k2": 75, "ki": 60}
    body = client.get("/api/chart", params=params).json()
    assert [lv["label"] for lv in body["levels"]] == ["KO", "K1", "K2", "KI"]


def test_chart_omits_blank_levels(client):
    body = client.get("/api/chart", params={"symbol": "6758", "ko": 100}).json()
    assert [lv["name"] for lv in body["levels"]] == ["KO"]


def test_invalid_symbol_is_400(client):
    res = client.get("/api/chart", params={"symbol": "2330.TW"})
    assert res.status_code == 400


def test_unknown_symbol_is_404(client):
    res = client.get("/api/chart", params={"symbol": "ZZZZ"})
    assert res.status_code == 404
    assert "ZZZZ" in res.json()["detail"]


def test_non_positive_pct_is_422(client):
    res = client.get("/api/chart", params={"symbol": "TSM", "ko": 0})
    assert res.status_code == 422


def test_index_page_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "lightweight-charts@4.2.2" in res.text


def test_logo_returns_svg_with_security_headers(client, monkeypatch):
    seen = []

    def fake_logo(symbol, exchange):
        seen.append((symbol, exchange))
        return b"<svg></svg>"

    monkeypatch.setattr(app_module.logos, "fetch_logo", fake_logo)
    res = client.get("/api/logo", params={"symbol": "6758.T", "exchange": "TSE"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/svg+xml"
    assert "default-src 'none'" in res.headers["content-security-policy"]
    assert seen == [("6758.T", "TSE")]


def test_logo_not_found_is_404(client, monkeypatch):
    monkeypatch.setattr(app_module.logos, "fetch_logo", lambda symbol, exchange: None)
    assert (
        client.get("/api/logo", params={"symbol": "MSFT", "exchange": "NASDAQ"}).status_code == 404
    )


def test_logo_rejects_bad_exchange(client):
    res = client.get("/api/logo", params={"symbol": "MSFT", "exchange": "../x"})
    assert res.status_code == 422
