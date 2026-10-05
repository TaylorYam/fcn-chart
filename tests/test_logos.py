import json

import pytest

from fcn_chart import logos

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18"><circle r="9"/></svg>'


@pytest.mark.parametrize(
    ("yahoo", "expected"), [("MSFT", "MSFT"), ("BRK-B", "BRK.B"), ("6758.T", "6758")]
)
def test_tradingview_code(yahoo, expected):
    assert logos.tradingview_code(yahoo) == expected


def test_pick_logoid_prefers_same_exchange():
    results = [
        {"symbol": "NVDA", "exchange": "TSX", "logoid": "nvidia-cdr"},
        {"symbol": "NVDA", "exchange": "NASDAQ", "logoid": "nvidia"},
    ]
    assert logos.pick_logoid(results, "NVDA", "NASDAQ") == "nvidia"


def test_pick_logoid_ignores_non_exact_symbols_and_bad_ids():
    results = [
        {"symbol": "NKE", "exchange": "NYSE", "logoid": "nike"},
        {"symbol": "BRK.B", "exchange": "NYSE", "logoid": "../evil"},
    ]
    assert logos.pick_logoid(results, "BRK.B", "NYSE") is None


def test_pick_logoid_falls_back_to_nested_logo_field():
    results = [{"symbol": "6758", "exchange": "TSE", "logo": {"logoid": "sony"}}]
    assert logos.pick_logoid(results, "6758", "TSE") == "sony"


@pytest.fixture
def fake_net(monkeypatch):
    calls = []
    responses = {}

    def fake_get(url):
        calls.append(url)
        result = responses.get("search" if "symbol_search" in url else "logo")
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(logos, "_get", fake_get)
    logos.clear_cache()
    yield calls, responses
    logos.clear_cache()


def search_body(*items):
    return json.dumps({"symbols": list(items)}).encode()


def test_fetch_logo_downloads_and_caches(fake_net):
    calls, responses = fake_net
    responses["search"] = search_body({"symbol": "6758", "exchange": "TSE", "logoid": "sony"})
    responses["logo"] = SVG
    assert logos.fetch_logo("6758.T", "TSE") == SVG
    assert logos.fetch_logo("6758.T", "TSE") == SVG
    assert len(calls) == 2  # 一次搜尋＋一次下載，第二次走快取
    assert calls[1].endswith("/sony.svg")
    assert "text=6758" in calls[0]


def test_fetch_logo_caches_not_found(fake_net):
    calls, responses = fake_net
    responses["search"] = search_body()
    assert logos.fetch_logo("ZZZZ", "NYSE") is None
    assert logos.fetch_logo("ZZZZ", "NYSE") is None
    assert len(calls) == 1


def test_fetch_logo_does_not_cache_network_errors(fake_net):
    calls, responses = fake_net
    responses["search"] = OSError("offline")
    assert logos.fetch_logo("MSFT", "NASDAQ") is None
    assert logos.fetch_logo("MSFT", "NASDAQ") is None
    assert len(calls) == 2


def test_fetch_logo_rejects_non_svg(fake_net):
    _, responses = fake_net
    responses["search"] = search_body(
        {"symbol": "MSFT", "exchange": "NASDAQ", "logoid": "microsoft"}
    )
    responses["logo"] = b"<html>not an svg</html>"
    assert logos.fetch_logo("MSFT", "NASDAQ") is None
