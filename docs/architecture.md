# Architecture Overview

## Purpose and scope

FCN Chart 是本機執行的小工具：輸入美股／日股代號與 KO/K/KI 百分比，產生標有三條水平線的日K線圖，下載 PNG 或複製圖片貼進 PPT。

不在範圍內：台股／港股、Step-down 等自訂額外線、與 `fcn-wt`／比價明細串接、多人或雲端部署。

## System context

```
使用者瀏覽器 ──HTTP──▶ 本機 FastAPI (127.0.0.1:8765) ──yfinance──▶ Yahoo Finance
                                   └──logo──▶ TradingView 代號搜尋／logo 圖庫
     │
     └──CDN──▶ unpkg (Lightweight Charts) / cdnjs (JSZip)
```

## Components and boundaries

| 模組 | 職責 |
| --- | --- |
| `src/fcn_chart/symbols.py` | 使用者輸入 → Yahoo 代號（4 碼數字開頭補 `.T`；`BRK.B` → `BRK-B`）；表格顯示代號（日股 `代號 JT`） |
| `src/fcn_chart/data.py` | 抓約 400 天日K、排除交易所當日未收盤（收盤後 20 分鐘緩衝）的K棒 |
| `src/fcn_chart/levels.py` | KO/K1/K2/KI：期初價 × % → 價位；美股 2 位、日股整數，四捨五入；單一履約價標示為 K |
| `src/fcn_chart/logos.py` | 公司 logo：以 TradingView 代號搜尋查 logoid，抓 `s3-symbol-logo.tradingview.com` 的 SVG，記憶體快取 |
| `src/fcn_chart/app.py` | `GET /` 頁面、`GET /api/chart?symbol=&ko=&k1=&k2=&ki=`、`GET /api/logo?symbol=&exchange=`（SVG 加 CSP 標頭） |
| `src/fcn_chart/static/` | TradingView 樣式作圖（圖例、TV logo）、FCN 參數表格、區間切換、匯出 32.2×14.4 公分 PNG（另建隱藏圖表截圖）、複製、zip |

價位計算在後端完成並有單元測試；前端只負責呈現與匯出。

## Data and state

無資料庫、無持久化。行情向 Yahoo 即時抓取，同一代號在記憶體快取 15 分鐘（`data.get_history`），服務重啟即清空。瀏覽器 `localStorage` 只記住上次輸入的代號與百分比。

## Runtime and deployment

- 本機 Windows，Python ≥ 3.11，以 `uv` 管理相依套件。
- 本機模式：雙擊 `start.bat`（= `uv run fcn-chart`），只綁定 127.0.0.1，自動開啟瀏覽器。
- 內網共用模式：雙擊 `start-server.bat`，先在 `main` 上 `git pull --ff-only` 自動更新，再以 `APP_HOST=0.0.0.0` 啟動，同事以 `http://<主機 IP>:8765/` 連線。無登入機制，只在公司內網使用；防火牆規則由使用者／IT 設定。
- 環境變數：`APP_PORT`（預設 8765）、`APP_HOST`（預設 127.0.0.1）。
- 公司網路的 HTTPS 檢查：啟動檔設定 `UV_NATIVE_TLS=1`；yfinance 連線使用 certifi＋Windows 憑證存放區合併的 PEM（`tls.ca_bundle_path`，寫在系統暫存資料夾）。

## Quality attributes and constraints

- 正確性：期初價必須是已收盤日K；價位四捨五入一致（避開 float 雜訊與銀行家捨入）。
- 需要網路連線（Yahoo、CDN）。
- 「複製圖片」需 Chromium 系瀏覽器（Edge／Chrome）且由使用者點擊觸發。

## Important decisions

- [0001: 以 yfinance 資料搭配 TradingView Lightweight Charts 作圖](adr/0001-lightweight-charts-with-yfinance.md)
