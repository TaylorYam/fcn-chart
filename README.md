# FCN Chart

FCN 標的快速作圖：輸入標的代號與 KO/K/KI 百分比，在 TradingView 風格的日K線圖上畫出對應水平線，一鍵下載 PNG 或複製圖片直接貼進 PPT。

## 使用方式

1. 雙擊 `start.bat`。第一次會自動安裝相依套件，之後瀏覽器會開啟 <http://127.0.0.1:8765/>。
2. 輸入標的代號，可一次多檔，用逗號或空白分隔：
   - 美股：`TSM`、`NVDA`、`BRK.B`
   - 日股：4 碼代號 `6758`（自動視為東證 `6758.T`）
3. 輸入 KO / K / KI 百分比（預設 100 / 80 / 70）。留空就不畫該線。
4. 按「產生圖表」。每張圖可切換 1M / 3M / 6M / YTD / 1Y，再按「下載 PNG」或「複製圖片」（到 PPT 按 Ctrl+V），或在上方按「全部下載（zip）」。

### 內網共用（給同事用）

架在你的電腦上，同事用瀏覽器連進來，不必各自安裝。

1. **主機（你的電腦）**：雙擊 `start-server.bat`。
   - 啟動前會自動 `git pull` 更新到 `main` 最新版（不在 `main` 分支時略過）。
   - 視窗會顯示「同事請用瀏覽器開啟：http://<你的 IP>:8765/」。
   - 第一次啟動時 Windows 防火牆若詢問，請只勾選「私人網路」並允許。
2. **同事**：用瀏覽器開啟視窗上顯示的網址即可，不需安裝任何東西。
3. 注意事項：
   - 主機要開著、且連在公司網路上；換網路（例如改用手機熱點）IP 會變，同事就連不到。
   - 只在公司網路使用，不要在公共 Wi-Fi 開 `start-server.bat`（沒有登入機制，同網路的人都能使用）。
   - `start.bat`（只限本機）與 `start-server.bat` 用同一個連接埠，一次只開一個；主機上自己用也直接開 <http://127.0.0.1:8765/>。
   - 同一檔行情會快取 15 分鐘，降低多人同時使用時對 Yahoo 的請求量。

### 計算規則

- **期初價（100%）**：最後一根**已收盤**日K的收盤價。交易所盤中（或收盤後 20 分鐘內）會排除當天未完成的K棒。
- **價格**：只還原分割、不還原股息，與 TradingView 預設顯示相同。
- **價位**：期初價 × %，美股四捨五入到小數 2 位，日股到整數日圓。

### 資料來源

行情來自 Yahoo Finance（透過 yfinance），圖表使用開源的 TradingView Lightweight Charts，版面比照 TradingView 網站預設淺色主題，不需要 TradingView 帳號。圖上不標示資料來源，需要時請在簡報註明。Yahoo 資料條款為個人用途，用於正式對客戶文件前請確認法遵要求。詳見 [ADR 0001](docs/adr/0001-lightweight-charts-with-yfinance.md)。

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
