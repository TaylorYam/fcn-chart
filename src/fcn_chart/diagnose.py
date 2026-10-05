"""連線診斷：`uv run python -m fcn_chart.diagnose`（或雙擊 diagnose.bat）。

逐一測試各種連線方式能否連到 Yahoo、TradingView、CDN，結果印出並存成 diagnose.txt，
方便在公司電腦找出「查無資料」的真正原因（憑證、proxy 或網站被封鎖）。
"""

import platform
import sys
import traceback
import urllib.request
from collections.abc import Callable
from pathlib import Path

import certifi
import curl_cffi
import yfinance as yf
from curl_cffi import requests as curl_requests

from fcn_chart import data, network

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/MSFT?range=5d&interval=1d"
TV_URL = "https://symbol-search.tradingview.com/symbol_search/v3/?text=MSFT&search_type=stocks"
CDN_URL = (
    "https://unpkg.com/lightweight-charts@4.2.2/dist/lightweight-charts.standalone.production.js"
)
UA = {"User-Agent": "Mozilla/5.0", "Origin": "https://www.tradingview.com"}
REPORT = Path("diagnose.txt")

lines: list[str] = []


def out(text: str = "") -> None:
    print(text, flush=True)
    lines.append(text)


def summarize(exc: BaseException, limit: int = 400) -> str:
    text = f"{type(exc).__name__}: {' '.join(str(exc).split())}"
    return text if len(text) <= limit else text[:limit] + "…"


def check(name: str, func: Callable[[], str]) -> bool:
    try:
        out(f"[OK]   {name}：{func()}")
        return True
    except Exception as exc:  # 診斷工具：任何錯誤都要記錄下來
        out(f"[FAIL] {name}：{summarize(exc)}")
        return False


def via_urllib(url: str) -> str:
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=15) as response:
        return f"HTTP {response.status}，{len(response.read())} bytes"


def via_curl(url: str, verify, proxies) -> str:
    session = curl_requests.Session(impersonate="chrome", verify=verify, proxies=proxies or None)
    response = session.get(url, headers=UA, timeout=15)
    return f"HTTP {response.status_code}，{len(response.content)} bytes"


def windows_pac() -> str:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        return winreg.QueryValueEx(key, "AutoConfigURL")[0]
    except (ImportError, OSError):
        return "（無）"


def main() -> None:
    out("== FCN Chart 連線診斷 ==")
    out(f"Python {sys.version.split()[0]}｜{platform.platform()}")
    out(f"yfinance {yf.__version__}｜curl_cffi {curl_cffi.__version__}")
    out()
    out("-- Proxy --")
    out(f"環境變數：{urllib.request.getproxies_environment() or '（無）'}")
    if hasattr(urllib.request, "getproxies_registry"):
        out(f"Windows 設定：{urllib.request.getproxies_registry() or '（無）'}")
    out(f"PAC 自動設定檔：{windows_pac()}")
    proxies = network.system_proxies()
    out(f"程式採用：{proxies or '（直連）'}")
    out()
    out("-- 憑證 --")
    out(f"Windows 憑證存放區（伺服器驗證用）：{len(network.windows_certificates())} 張")
    bundle = network.ca_bundle_path()
    out(f"合併憑證檔：{bundle}")
    out()
    out("-- Yahoo（行情） --")
    check("urllib（Windows 憑證＋系統 proxy）", lambda: via_urllib(YAHOO_URL))
    check("curl_cffi（合併憑證＋程式採用的 proxy）", lambda: via_curl(YAHOO_URL, bundle, proxies))
    check("curl_cffi（只用 certifi）", lambda: via_curl(YAHOO_URL, certifi.where(), proxies))
    if proxies:
        check("curl_cffi（合併憑證、不經 proxy）", lambda: via_curl(YAHOO_URL, bundle, None))
    check("程式實際抓 MSFT 日K", lambda: f"{len(data.fetch_history('MSFT').candles)} 根K棒")
    out()
    out("-- 其他網站 --")
    check("TradingView（公司 logo）", lambda: via_urllib(TV_URL))
    check("unpkg（圖表元件，瀏覽器載入）", lambda: via_urllib(CDN_URL))
    out()
    out("請把上面整段結果（或同資料夾的 diagnose.txt）傳給維護者。")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        out(traceback.format_exc())
    finally:
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
