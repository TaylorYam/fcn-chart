"""行情資料：用 yfinance 抓日K，並排除尚未收盤的當日K棒。"""

import threading
import time as clock
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl_requests
from yfinance import exceptions as yf_errors

from fcn_chart.network import ca_bundle_path, system_proxies

# yfinance 預設會吞掉例外、只回傳空資料，連線失敗也會變成「查無資料」；改為拋出例外再分類。
yf.config.debug.hide_exceptions = False

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
    """抓日K。auto_adjust=False：價格只還原分割、不還原股息（等同 TradingView 預設）。"""
    now = now or datetime.now(tz=ZoneInfo("UTC"))
    ticker = yf.Ticker(symbol, session=yahoo_session())
    start = (now - timedelta(days=HISTORY_DAYS)).date()
    df = download_daily(ticker, symbol, start.isoformat())
    if df.empty:
        raise SymbolNotFoundError(f"查無資料：{symbol}")

    timezone = str(df.index.tz) if df.index.tz else _fast_info(ticker, "timezone", "UTC")
    candles = to_candles(drop_unfinished_bar(df, timezone, now))
    if not candles:
        raise SymbolNotFoundError(f"查無已收盤的日K：{symbol}")

    return PriceHistory(
        symbol=symbol,
        name=_display_name(ticker, symbol),
        exchange=exchange_name(_fast_info(ticker, "exchange", "")),
        currency=_fast_info(ticker, "currency", "USD").upper(),
        timezone=timezone,
        candles=candles,
    )


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


def download_daily(ticker: yf.Ticker, symbol: str, start: str) -> pd.DataFrame:
    try:
        return ticker.history(start=start, interval="1d", auto_adjust=False)
    except (yf_errors.YFTickerMissingError, yf_errors.YFTzMissingError) as exc:
        raise SymbolNotFoundError(f"查無資料：{symbol}") from exc
    except yf_errors.YFRateLimitError as exc:
        raise DataSourceError("Yahoo 暫時限制查詢次數，請稍後再試") from exc
    except (OSError, yf_errors.YFException) as exc:
        # 代號不存在時 Yahoo 回 HTTP 404；其餘 curl_cffi 錯誤（OSError 子類別）
        # 多半是憑證、proxy 或網站被封鎖。
        if getattr(getattr(exc, "response", None), "status_code", None) == 404:
            raise SymbolNotFoundError(f"查無資料：{symbol}") from exc
        raise DataSourceError(f"無法連線到 Yahoo：{_short(exc)}") from exc


def _short(exc: Exception, limit: int = 300) -> str:
    text = " ".join(str(exc).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _volume(value) -> float:
    # 成交量偶爾是 NaN；NaN 不能放進 JSON。
    return float(value) if pd.notna(value) else 0.0


def exchange_name(code: str) -> str:
    return EXCHANGE_NAMES.get(code.upper(), code.upper())


def _fast_info(ticker: yf.Ticker, key: str, default: str) -> str:
    try:
        return ticker.fast_info[key] or default
    except Exception:
        return default


def _display_name(ticker: yf.Ticker, fallback: str) -> str:
    # info 偶爾會失敗或很慢；拿不到名稱不影響作圖。
    try:
        info = ticker.info
        # shortName 常被截斷（如 "Taiwan Semiconductor Manufactur"），優先用 longName。
        return info.get("longName") or info.get("shortName") or fallback
    except Exception:
        return fallback
