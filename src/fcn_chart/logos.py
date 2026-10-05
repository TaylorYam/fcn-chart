"""公司 logo：與 TradingView 網站圖例相同的 logo。

TradingView 沒有官方 logo API：先用其網站的代號搜尋查出 logoid，再到 logo 圖庫抓 SVG。
只取 logo、不取行情資料；介面改版或連線失敗時回傳 None，前端就不顯示 logo。
"""

import json
import re
import threading
import urllib.parse
import urllib.request

from fcn_chart.symbols import JP_SUFFIX

SEARCH_URL = "https://symbol-search.tradingview.com/symbol_search/v3/"
LOGO_URL = "https://s3-symbol-logo.tradingview.com/{logoid}.svg"
HEADERS = {"Origin": "https://www.tradingview.com", "User-Agent": "Mozilla/5.0"}
TIMEOUT_SECONDS = 10
MAX_SVG_BYTES = 200_000
LOGOID = re.compile(r"^[a-z0-9][a-z0-9-]*(/[a-z0-9-]+)*$")

_cache: dict[tuple[str, str], bytes | None] = {}
_cache_lock = threading.Lock()


def tradingview_code(yahoo_symbol: str) -> str:
    """Yahoo 代號 → TradingView 代號：6758.T → 6758、BRK-B → BRK.B。"""
    if yahoo_symbol.endswith(JP_SUFFIX):
        return yahoo_symbol[: -len(JP_SUFFIX)]
    return yahoo_symbol.replace("-", ".")


def pick_logoid(results: list[dict], code: str, exchange: str) -> str | None:
    """從搜尋結果挑出代號完全相同者；同交易所優先。"""
    exact = [r for r in results if r.get("symbol", "").upper() == code.upper()]
    preferred = [r for r in exact if r.get("exchange", "").upper() == exchange.upper()]
    for r in preferred or exact:
        logoid = r.get("logoid") or (r.get("logo") or {}).get("logoid")
        if logoid and LOGOID.match(logoid):
            return logoid
    return None


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read(MAX_SVG_BYTES + 1)


def search_logoid(code: str, exchange: str) -> str | None:
    query = urllib.parse.urlencode(
        {"text": code, "hl": 0, "exchange": exchange, "lang": "en", "search_type": "stocks"}
    )
    results = json.loads(_get(f"{SEARCH_URL}?{query}")).get("symbols", [])
    return pick_logoid(results, code, exchange)


def download_logo(logoid: str) -> bytes | None:
    svg = _get(LOGO_URL.format(logoid=logoid))
    if len(svg) > MAX_SVG_BYTES or b"<svg" not in svg[:1000]:
        return None
    return svg


def fetch_logo(yahoo_symbol: str, exchange: str) -> bytes | None:
    """取得 logo SVG；結果（含查無）快取在記憶體，同一代號只向 TradingView 查一次。"""
    key = (yahoo_symbol, exchange)
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    try:
        logoid = search_logoid(tradingview_code(yahoo_symbol), exchange)
        svg = download_logo(logoid) if logoid else None
    except (OSError, ValueError):
        # 連線失敗不快取，下次再試；ValueError 涵蓋 JSON 解析錯誤。
        return None
    with _cache_lock:
        _cache[key] = svg
    return svg


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
