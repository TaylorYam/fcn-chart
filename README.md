# FCN Chart

FCN 標的快速作圖：輸入標的代號與 KO/K1/K2/KI 百分比，在 TradingView 風格的日K線圖上畫出對應水平線，一鍵下載 PNG 或複製圖片直接貼進 PPT。

## 使用方式

1. 雙擊 `start.bat`。第一次會自動安裝相依套件，之後瀏覽器會開啟 <http://127.0.0.1:8765/>。
2. 輸入標的代號，最多 5 檔，每格一檔（同一組參數套用到每一檔，各出一張圖）：
   - 美股：`TSM`、`NVDA`、`BRK.B`
   - 日股：4 碼代號 `6758`（自動視為東證 `6758.T`）
3. 輸入 KO / K1 / K2 / KI 百分比（預設 100 / 80 / 空白 / 70）。留空就不畫該線；K1、K2 只填一個時標示為「K」。
4. 按「產生圖表」。每張圖可切換 1M / 3M / 6M / YTD / 1Y（圖表已鎖定縮放與拖曳，區間只能用這些頁籤切換），再按「下載 PNG」或「複製圖片」（到 PPT 按 Ctrl+V），或在上方按「全部下載（zip）」。

### 公司電腦／公司網路

- 公司網路常以自有根憑證檢查 HTTPS。`start.bat` 已設定 `UV_NATIVE_TLS=1`，程式抓行情時也會一併信任 Windows 憑證存放區，不需另外設定。
- 抓不到資料時，畫面會顯示真正原因（例如「無法連線到 Yahoo：…」）；可雙擊 **`diagnose.bat`** 測試各種連線方式，結果存成 `diagnose.txt`，傳給維護者判斷。
- 程式會使用環境變數或 Windows 網際網路設定中的 proxy（不支援 PAC 自動設定檔）。
- 若仍出現 `invalid peer certificate` 或連不上 `pypi.org`、Yahoo，代表公司直接封鎖這些網站，需請 IT 開放：`pypi.org`、`files.pythonhosted.org`（第一次安裝套件）、`*.yahoo.com`（行情）、`unpkg.com`、`cdnjs.cloudflare.com`（圖表元件）、`*.tradingview.com`（公司 logo）。
- 從 GitHub 下載 zip 解壓縮的版本不會自動更新，改版時需重新下載。

### 圖上內容

- 價位線標籤：KO 放在左側（KO 通常是 100%，放右側會擋住最新的K棒），K／K1／K2／KI 在右側。
- TradingView 網站預設淺色樣式：K線、左上角 OHLC 圖例（名稱左邊有公司 logo）、左下角 TV logo（不含成交量）。
- 圖例下方的白底表格：`連結標的｜參考最新價｜K…｜KI`，表頭百分比與數字隨輸入連動（KO 不列入表格）；數字為粗體，價位顏色與對應的線相同。連結標的美股只顯示代號（`MSFT`），日股為 `6758 JT`。
- 圖片為 3651 × 1633 px（PPT 尺寸 **32.2 × 14.4 公分** 的 3 倍解析度）。「下載 PNG」有寫入 288 DPI，插入 PPT 即為 32.2 × 14.4 公分；「複製圖片」貼上時瀏覽器會丟掉 DPI，PPT 會縮成投影片寬，請在 PPT 調整大小（解析度不受影響）。

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

行情來自 Yahoo Finance（直接呼叫其 chart API），圖表使用開源的 TradingView Lightweight Charts，版面比照 TradingView 網站預設淺色主題，不需要 TradingView 帳號。公司 logo 取自 TradingView 的 logo 圖庫（經由其非官方代號搜尋查詢，失效時只是不顯示 logo）。圖上不標示資料來源，需要時請在簡報註明。Yahoo 資料條款為個人用途，用於正式對客戶文件前請確認法遵要求。詳見 [ADR 0001](docs/adr/0001-lightweight-charts-with-yfinance.md)。

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
