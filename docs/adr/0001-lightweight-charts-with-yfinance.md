# 0001: 以 yfinance 資料搭配 TradingView Lightweight Charts 作圖

- Status: Accepted
- Date: 2026-10-05

## Context

需要在「TradingView 風格」的日K線圖上自動畫出 FCN 的 KO/K/KI 水平線，並匯出 PNG 貼進 PPT。TradingView 沒有公開的行情資料 API；免費嵌入 widget 不提供程式化畫線；可畫線的 Advanced Charts 需申請授權，個人或內部工具通常不會核准。

## Decision

- 資料：以 yfinance（Yahoo Finance）抓日K，`auto_adjust=False`（只還原分割、不還原股息，等同 TradingView 預設顯示）。
- 作圖：前端使用開源的 TradingView Lightweight Charts v4.2.2，以 `createPriceLine` 畫水平線、`takeScreenshot` 匯出圖片。做法沿用 `TaylorYam/Huda-taiwan-market-quant` 的K線設定。
- 關閉圖上的 TV logo（`attributionLogo: false`），改在畫面與匯出圖註腳標示「資料來源：Yahoo Finance｜Chart: TradingView Lightweight Charts」，滿足 Apache 2.0 attribution 並避免誤認資料來自 TradingView。

## Alternatives considered

- Playwright 自動操作 tradingview.com 畫線截圖：資料與外觀完全是 TradingView，但依賴非官方內部介面、需處理登入與彈窗、改版即壞，且有服務條款疑慮。
- TradingView 嵌入 widget：無法程式化畫線；在 iframe 上疊線拿不到價格座標。
- tvDatafeed 等非官方資料套件：不穩定，同樣有服務條款疑慮。
- Plotly / matplotlib：可行但不是 TradingView 風格。

## Consequences

- 不需 TradingView 帳號，不連 tradingview.com。
- 資料準確度取決於 Yahoo Finance；Yahoo 條款為個人用途，若要放進正式對客戶簡報需確認法遵要求。資料層集中在 `src/fcn_chart/data.py`，日後可換成授權資料源。
- 前端從 CDN 載入 Lightweight Charts 與 JSZip，需要網路連線。
