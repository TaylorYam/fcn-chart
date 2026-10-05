"""FastAPI 服務：提供作圖頁面與 /api/chart。"""

from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fcn_chart import data
from fcn_chart.levels import compute_levels, price_decimals, round_half_up
from fcn_chart.symbols import InvalidSymbolError, normalize_symbol

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="FCN Chart")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

Pct = Annotated[float | None, Query(gt=0, le=1000)]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/chart")
def chart(symbol: str, ko: Pct = None, k: Pct = None, ki: Pct = None) -> dict:
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
    levels = compute_levels(ref_close, {"KO": ko, "K": k, "KI": ki}, history.currency)
    return {
        "input": symbol.strip(),
        "symbol": history.symbol,
        "name": history.name,
        "exchange": history.exchange,
        "currency": history.currency,
        "decimals": price_decimals(history.currency),
        "ref_date": ref.time,
        "ref_close": ref_close,
        "levels": [asdict(level) for level in levels],
        "candles": [asdict(c) for c in history.candles],
    }
