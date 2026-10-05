"""行情資料：直接呼叫 Yahoo 的 chart API 抓日K，並排除尚未收盤的當日K棒。

不使用 yfinance：它在抓K線前會先向 Yahoo 取 cookie／crumb，這一步在公司網路
（共用出口、HTTPS 檢查）常被 Yahoo 以 HTTP 429 拒絕。chart API 單一請求、不需 crumb，
一次就有K線、幣別、交易所、時區與公司名稱。
"""

import threading
import time as clock
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from curl_cffi import requests as curl_requests

from fcn_chart.network import ca_bundle_path, system_proxies

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TIMEOUT_SECONDS = 20

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

# 抓略多於 1 年，確保「1Y」區間有完整約 252 根K棒。
HISTORY_DAYS = 400


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
    start = now - timedelta(days=HISTORY_DAYS)
    return parse_chart(symbol, request_chart(symbol, start, now), now)


def request_chart(symbol: str, start: datetime, end: datetime) -> dict:
    params = {
        "period1": int(start.timestamp()),
        "period2": int(end.timestamp()),
        "interval": "1d",
        "events": "div,splits",
    }
    url = CHART_URL.format(symbol=urllib.parse.quote(symbol, safe=""))
    try:
        response = yahoo_session().get(url, params=params, timeout=TIMEOUT_SECONDS)
    except OSError as exc:
        # curl_cffi 的錯誤都是 OSError 的子類別：憑證、proxy、被封鎖、逾時。
        raise DataSourceError(f"無法連線到 Yahoo：{_short(exc)}") from exc
    if response.status_code == 404:
        raise SymbolNotFoundError(f"查無資料：{symbol}")
    if response.status_code == 429:
        raise DataSourceError("Yahoo 暫時限制查詢次數，請稍後再試")
    if response.status_code != 200:
        raise DataSourceError(f"Yahoo 回應異常：HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise DataSourceError("Yahoo 回應格式異常（可能被公司網路攔截）") from exc


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
