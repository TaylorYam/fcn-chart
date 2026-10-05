# FCN Chart

FCN 標的快速作圖：輸入標的代號與 KO/K/KI 百分比，在 TradingView 風格的日K線圖上畫出對應水平線，一鍵下載 PNG 或複製圖片直接貼進 PPT。

## 使用方式

1. 雙擊 `start.bat`。第一次會自動安裝相依套件，之後瀏覽器會開啟 <http://127.0.0.1:8765/>。
2. 輸入標的代號，可一次多檔，用逗號或空白分隔：
   - 美股：`TSM`、`NVDA`、`BRK.B`
   - 日股：4 碼代號 `6758`（自動視為東證 `6758.T`）
3. 輸入 KO / K / KI 百分比（預設 100 / 80 / 70）。留空就不畫該線。
4. 按「產生圖表」。每張圖可切換 1M / 3M / 6M / 1Y，再按「下載 PNG」或「複製圖片」（到 PPT 按 Ctrl+V），或在上方按「全部下載（zip）」。

### 計算規則

- **期初價（100%）**：最後一根**已收盤**日K的收盤價。交易所盤中（或收盤後 20 分鐘內）會排除當天未完成的K棒。
- **價格**：只還原分割、不還原股息，與 TradingView 預設顯示相同。
- **價位**：期初價 × %，美股四捨五入到小數 2 位，日股到整數日圓。

### 資料來源

行情來自 Yahoo Finance（透過 yfinance），圖表使用開源的 TradingView Lightweight Charts，不需要 TradingView 帳號。圖上註腳會標示兩者。Yahoo 資料條款為個人用途，用於正式對客戶文件前請確認法遵要求。詳見 [ADR 0001](docs/adr/0001-lightweight-charts-with-yfinance.md)。

## 開發

需求：Python ≥ 3.11、[uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run fcn-chart
```

架構說明見 [docs/architecture.md](docs/architecture.md)。

## 協作流程

AI 協作規範見 [AGENTS.md](AGENTS.md)。一般變更流程：

`Issue → branch → plan → implementation → validation → commit and push → pull request → review and CI → merge`

`main` 保持穩定，變更走 task branch 與 PR。
