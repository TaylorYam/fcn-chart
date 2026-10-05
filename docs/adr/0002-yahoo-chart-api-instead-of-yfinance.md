# 0002: 直接呼叫 Yahoo chart API，取代 yfinance

- Status: Accepted
- Date: 2026-10-05

## Context

公司電腦（有 HTTPS 檢查、需經 `proxy.esunsec.com.tw:8080`）所有代號都抓不到資料。診斷（#15）顯示：憑證與 proxy 處理後，直接呼叫 `query1.finance.yahoo.com/v8/finance/chart` 可取得 HTTP 200；但 yfinance 在抓K線前會先取 cookie／crumb，這一步被 Yahoo 以 HTTP 429 拒絕，導致整個查詢失敗。

## Decision

- 移除 yfinance，`data.py` 以 curl_cffi（模擬 Chrome、合併憑證、系統 proxy）直接呼叫 chart API，每檔一個請求。
- chart API 的 `meta` 已含幣別、交易所、時區、`longName`；`indicators.quote` 的開高低收為「只還原分割、不還原股息」，與原本 `auto_adjust=False` 相同。

## Alternatives considered

- 繼續用 yfinance 並重試：crumb 被拒時重試無效。
- 換資料源（Stooq、付費 API）：需另行評估覆蓋率、授權與公司網路是否開放；目前 Yahoo chart API 在公司網路可用。

## Consequences

- 請求數減少（不再取 crumb、quoteSummary、fast_info），在共用出口 IP 下較不易被限流。
- 依賴 Yahoo 未公開的 chart API 格式；格式改變時需調整 `parse_chart`。資料取得仍集中在 `data.py`，日後可換授權資料源。
- ADR 0001 中「以 yfinance 抓日K」的部分由本 ADR 取代，其餘決定不變。
