"""FastAPI 服務：提供作圖頁面、/api/chart 與 /api/logo。"""

from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from fcn_chart import data, logos
from fcn_chart.levels import compute_levels, price_decimals, round_half_up
from fcn_chart.symbols import InvalidSymbolError, display_ticker, normalize_symbol

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="FCN Chart")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

Pct = Annotated[float | None, Query(gt=0, le=1000)]
Exchange = Annotated[str, Query(pattern=r"^[A-Z]{0,10}$")]

# logo 是外部來的 SVG：禁止腳本與外部資源，直接開啟網址時也不會在本站執行任何東西。
SVG_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "public, max-age=86400",
}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/chart")
def chart(symbol: str, ko: Pct = None, k1: Pct = None, k2: Pct = None, ki: Pct = None) -> dict:
    try:
        yahoo_symbol = normalize_symbol(symbol)
    except InvalidSymbolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        history = data.get_history(yahoo_symbol)
    except data.SymbolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ref = history.ref_candle
    # Yahoo 價格是 float32 轉來的（如 472.7799987），先去掉雜訊再算，避免臨界值進位錯誤。
    ref_close = round_half_up(ref.close, 4)
    pcts = {"KO": ko, "K1": k1, "K2": k2, "KI": ki}
    levels = compute_levels(ref_close, pcts, history.currency)
    return {
        "input": symbol.strip(),
        "symbol": history.symbol,
        "ticker": display_ticker(history.symbol),
        "name": history.name,
        "exchange": history.exchange,
        "currency": history.currency,
        "decimals": price_decimals(history.currency),
        "ref_date": ref.time,
        "ref_close": ref_close,
        "levels": [asdict(level) for level in levels],
        "candles": [asdict(c) for c in history.candles],
    }


@app.get("/api/logo")
def logo(symbol: str, exchange: Exchange = "") -> Response:
    try:
        yahoo_symbol = normalize_symbol(symbol)
    except InvalidSymbolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    svg = logos.fetch_logo(yahoo_symbol, exchange)
    if svg is None:
        raise HTTPException(status_code=404, detail=f"查無 logo：{symbol}")
    return Response(content=svg, media_type="image/svg+xml", headers=SVG_HEADERS)
