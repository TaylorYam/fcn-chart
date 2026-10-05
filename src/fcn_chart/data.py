"""行情資料：直接呼叫 Yahoo 的 chart API 抓日K，並排除尚未收盤的當日K棒。

不使用 yfinance：它在抓K線前會先向 Yahoo 取 cookie／crumb，這一步在公司網路
（共用出口、HTTPS 檢查）常被 Yahoo 以 HTTP 429 拒絕。chart API 單一請求、不需 crumb，
一次就有K線、幣別、交易所、時區與公司名稱。

請求寫法刻意與公司電腦上診斷成功的請求一致（簡單的 User-Agent、range 參數）：
公司 HTTPS 檢查會改變連線特徵，若再宣稱是完整的 Chrome，容易被 Yahoo 判為機器人（429）。
curl_cffi 被擋或連不上時，改用 urllib（Windows 憑證＋系統 proxy）再試一次。
"""

import json
import threading
import time as clock
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from curl_cffi import requests as curl_requests

from fcn_chart.network import ca_bundle_path, ssl_context, system_proxies

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# 2 年確保「1Y」區間有完整約 252 根K棒。
CHART_PARAMS = {"range": "2y", "interval": "1d"}
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
TIMEOUT_SECONDS = 20
RATE_LIMITED = "Yahoo 暫時限制查詢次數，請稍後再試"

# 交易所收盤時間（交易所當地時間）。收盤後再多等一段緩衝，讓 Yahoo 的日K定稿。
MARKET_CLOSE = {
    "America/New_York": time(16, 0),
    "Asia/Tokyo": time(15, 30),
}
SETTLE_BUFFER = timedelta(minutes=20)

# Yahoo 交易所代碼 → TradingView 顯示的交易所名稱（圖例用）。
EXCHANGE_NAMES = {
    "NYQ": "NYSE",
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NAS": "NASDAQ",
    "ASE": "AMEX",
    "PCX": "AMEX",
    "BTS": "CBOE",
    "JPX": "TSE",
}

# 同一代號的行情快取秒數：多人共用時降低對 Yahoo 的請求量。
CACHE_TTL_SECONDS = 15 * 60


class SymbolNotFoundError(LookupError):
    pass


class DataSourceError(RuntimeError):
    """連不上 Yahoo 或被限流等，跟代號本身無關的錯誤。"""


@dataclass(frozen=True)
class Candle:
    time: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class PriceHistory:
    symbol: str
    name: str
    exchange: str
    currency: str
    timezone: str
    candles: list[Candle]

    @property
    def ref_candle(self) -> Candle:
        return self.candles[-1]


def drop_unfinished_bar(df: pd.DataFrame, timezone: str, now: datetime) -> pd.DataFrame:
    """若最後一根K棒是交易所「今天」且尚未收盤（含緩衝），就把它拿掉。"""
    if df.empty:
        return df

    tz = ZoneInfo(timezone)
    local_now = now.astimezone(tz)
    last_date = pd.Timestamp(df.index[-1]).date()
    if last_date != local_now.date():
        return df

    close_time = MARKET_CLOSE.get(timezone, time(16, 0))
    settled_at = datetime.combine(local_now.date(), close_time, tzinfo=tz) + SETTLE_BUFFER
    if local_now < settled_at:
        return df.iloc[:-1]
    return df


def to_candles(df: pd.DataFrame) -> list[Candle]:
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return [
        Candle(
            time=pd.Timestamp(idx).strftime("%Y-%m-%d"),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=_volume(row.get("Volume")),
        )
        for idx, row in df.iterrows()
    ]


def fetch_history(symbol: str, now: datetime | None = None) -> PriceHistory:
    """抓日K。chart API 的開高低收只還原分割、不還原股息（等同 TradingView 預設）。"""
    now = now or datetime.now(tz=ZoneInfo("UTC"))
    return parse_chart(symbol, request_chart(symbol), now)


def request_chart(symbol: str) -> dict:
    url = CHART_URL.format(symbol=urllib.parse.quote(symbol, safe=""))
    errors: list[str] = []
    for transport in (get_via_curl, get_via_urllib):
        try:
            status, body = transport(url)
        except OSError as exc:
            # 憑證、proxy、被封鎖、逾時；curl_cffi 與 urllib 的連線錯誤都是 OSError。
            errors.append(f"無法連線到 Yahoo：{_short(exc)}")
            continue
        if status == 429:
            errors.append(RATE_LIMITED)
            continue
        return decode_chart(symbol, status, body)
    raise DataSourceError("；".join(dict.fromkeys(errors)))


def decode_chart(symbol: str, status: int, body: bytes) -> dict:
    if status == 404:
        raise SymbolNotFoundError(f"查無資料：{symbol}")
    if status != 200:
        raise DataSourceError(f"Yahoo 回應異常：HTTP {status}")
    try:
        return json.loads(body)
    except ValueError as exc:
        raise DataSourceError("Yahoo 回應格式異常（可能被公司網路攔截）") from exc


def get_via_curl(url: str) -> tuple[int, bytes]:
    response = yahoo_session().get(
        url, params=CHART_PARAMS, headers=HEADERS, timeout=TIMEOUT_SECONDS
    )
    return response.status_code, response.content


def get_via_urllib(url: str) -> tuple[int, bytes]:
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(CHART_PARAMS)}", headers=HEADERS
    )
    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT_SECONDS, context=ssl_context()
        ) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        # HTTP 錯誤碼（404、429…）也算有回應，交給呼叫端判斷。
        return exc.code, exc.read()


def parse_chart(symbol: str, payload: dict, now: datetime) -> PriceHistory:
    results = (payload.get("chart") or {}).get("result") or []
    if not results or not results[0].get("timestamp"):
        raise SymbolNotFoundError(f"查無資料：{symbol}")
    result = results[0]
    meta = result.get("meta", {})
    timezone = meta.get("exchangeTimezoneName") or "America/New_York"

    candles = to_candles(drop_unfinished_bar(chart_to_frame(result, timezone), timezone, now))
    if not candles:
        raise SymbolNotFoundError(f"查無已收盤的日K：{symbol}")

    return PriceHistory(
        symbol=symbol,
        # shortName 常被截斷（如 "Taiwan Semiconductor Manufactur"），優先用 longName。
        name=meta.get("longName") or meta.get("shortName") or symbol,
        exchange=exchange_name(meta.get("exchangeName", "")),
        currency=(meta.get("currency") or "USD").upper(),
        timezone=timezone,
        candles=candles,
    )


def chart_to_frame(result: dict, timezone: str) -> pd.DataFrame:
    """chart API 結果 → 以交易所當地日期為索引的開高低收量。"""
    quote = result["indicators"]["quote"][0]
    blank = [None] * len(result["timestamp"])
    index = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(timezone).normalize()
    columns = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    df = pd.DataFrame(
        {
            name: pd.to_numeric(pd.Series(quote.get(key) or blank, dtype="object"))
            for name, key in columns.items()
        }
    )
    df.index = index
    # 盤中時最後一根的時間戳是「現在」，正規化成日期後可能與前一筆重複，保留最新的。
    return df[~df.index.duplicated(keep="last")]


_cache: dict[str, tuple[float, PriceHistory]] = {}
_cache_lock = threading.Lock()


def get_history(symbol: str) -> PriceHistory:
    """有快取的 fetch_history：同一代號 CACHE_TTL_SECONDS 內重複查詢直接回傳上次結果。"""
    now = clock.monotonic()
    with _cache_lock:
        hit = _cache.get(symbol)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    history = fetch_history(symbol)
    with _cache_lock:
        _cache[symbol] = (now, history)
    return history


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def yahoo_session() -> curl_requests.Session:
    """信任 Windows 憑證存放區並使用系統 proxy，公司網路才連得上。"""
    return curl_requests.Session(
        impersonate="chrome", verify=ca_bundle_path(), proxies=system_proxies() or None
    )


def _short(exc: Exception, limit: int = 300) -> str:
    text = " ".join(str(exc).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _volume(value) -> float:
    # 成交量偶爾是 NaN；NaN 不能放進 JSON。
    return float(value) if pd.notna(value) else 0.0


def exchange_name(code: str) -> str:
    return EXCHANGE_NAMES.get(code.upper(), code.upper())
