from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from fcn_chart import data
from fcn_chart.data import (
    DataSourceError,
    SymbolNotFoundError,
    drop_unfinished_bar,
    exchange_name,
    parse_chart,
    request_chart,
    to_candles,
)

NY = "America/New_York"
TOKYO = "Asia/Tokyo"


def make_df(dates, tz):
    index = pd.DatetimeIndex([pd.Timestamp(d, tz=tz) for d in dates])
    n = len(dates)
    return pd.DataFrame(
        {
            "Open": [1.0] * n,
            "High": [2.0] * n,
            "Low": [0.5] * n,
            "Close": range(10, 10 + n),
            "Volume": [1000.0] * n,
        },
        index=index,
    )


def at(tz, *args):
    return datetime(*args, tzinfo=ZoneInfo(tz))


def test_keeps_all_bars_when_last_bar_is_previous_day():
    df = make_df(["2026-10-01", "2026-10-02"], NY)
    # 週一早上 9 點（美東），今天還沒有K棒。
    assert len(drop_unfinished_bar(df, NY, at(NY, 2026, 10, 5, 9, 0))) == 2


def test_drops_today_bar_during_us_session():
    df = make_df(["2026-10-02", "2026-10-05"], NY)
    out = drop_unfinished_bar(df, NY, at(NY, 2026, 10, 5, 11, 30))
    assert list(out["Close"]) == [10]


def test_drops_today_bar_within_settle_buffer():
    df = make_df(["2026-10-02", "2026-10-05"], NY)
    assert len(drop_unfinished_bar(df, NY, at(NY, 2026, 10, 5, 16, 10))) == 1


def test_keeps_today_bar_after_close():
    df = make_df(["2026-10-02", "2026-10-05"], NY)
    assert len(drop_unfinished_bar(df, NY, at(NY, 2026, 10, 5, 16, 30))) == 2


def test_tokyo_uses_local_date_and_close_time():
    df = make_df(["2026-10-02", "2026-10-05"], TOKYO)
    # 台北 14:06 = 東京 15:06，尚未收盤。
    taipei_now = datetime(2026, 10, 5, 14, 6, tzinfo=ZoneInfo("Asia/Taipei"))
    assert len(drop_unfinished_bar(df, TOKYO, taipei_now)) == 1
    taipei_evening = datetime(2026, 10, 5, 20, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert len(drop_unfinished_bar(df, TOKYO, taipei_evening)) == 2


def test_to_candles_formats_dates_and_skips_nan():
    df = make_df(["2026-10-01", "2026-10-02"], NY)
    df.loc[df.index[0], "Open"] = float("nan")
    candles = to_candles(df)
    assert [(c.time, c.close) for c in candles] == [("2026-10-02", 11.0)]


def test_to_candles_nan_volume_becomes_zero():
    df = make_df(["2026-10-01"], NY)
    df.loc[df.index[0], "Volume"] = float("nan")
    assert to_candles(df)[0].volume == 0.0


def test_exchange_name_maps_yahoo_codes_to_tradingview():
    assert exchange_name("NYQ") == "NYSE"
    assert exchange_name("NMS") == "NASDAQ"
    assert exchange_name("JPX") == "TSE"
    assert exchange_name("xyz") == "XYZ"


def chart_payload(timestamps, closes, tz="America/New_York", **meta):
    n = len(timestamps)
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "currency": "USD",
                        "exchangeName": "NMS",
                        "exchangeTimezoneName": tz,
                        "longName": "Microsoft Corporation",
                        **meta,
                    },
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": closes,
                                "high": closes,
                                "low": closes,
                                "close": closes,
                                "volume": [1000] * n,
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


# 2026-10-01、10-02 美東 09:30 開盤（UTC 13:30）
OCT1 = int(datetime(2026, 10, 1, 13, 30, tzinfo=ZoneInfo("UTC")).timestamp())
OCT2 = int(datetime(2026, 10, 2, 13, 30, tzinfo=ZoneInfo("UTC")).timestamp())
OCT5 = int(datetime(2026, 10, 5, 13, 30, tzinfo=ZoneInfo("UTC")).timestamp())


def test_parse_chart_builds_history_in_exchange_dates():
    history = parse_chart("MSFT", chart_payload([OCT1, OCT2], [510.0, 517.53]), at(NY, 2026, 10, 3))
    assert history.name == "Microsoft Corporation"
    assert history.exchange == "NASDAQ"
    assert history.currency == "USD"
    assert [(c.time, c.close) for c in history.candles] == [
        ("2026-10-01", 510.0),
        ("2026-10-02", 517.53),
    ]


def test_parse_chart_drops_unfinished_bar_and_nulls():
    payload = chart_payload([OCT1, OCT2, OCT5], [510.0, None, 520.0])
    history = parse_chart("MSFT", payload, at(NY, 2026, 10, 5, 11, 0))
    assert [c.time for c in history.candles] == ["2026-10-01"]


def test_parse_chart_falls_back_to_short_name():
    payload = chart_payload([OCT1], [510.0], longName=None, shortName="SONY GROUP")
    assert parse_chart("6758.T", payload, at(NY, 2026, 10, 3)).name == "SONY GROUP"


def test_parse_chart_without_result_is_not_found():
    payload = {"chart": {"result": None, "error": {"code": "Not Found"}}}
    with pytest.raises(SymbolNotFoundError):
        parse_chart("ZZZZ", payload, at(NY, 2026, 10, 3))


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self.body = body

    def json(self):
        if self.body is None:
            raise ValueError("not json")
        return self.body


class FakeSession:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def session(monkeypatch):
    holder = {}

    def use(outcome):
        holder["session"] = FakeSession(outcome)
        monkeypatch.setattr(data, "yahoo_session", lambda: holder["session"])
        return holder["session"]

    return use


START = at(NY, 2025, 9, 1)
END = at(NY, 2026, 10, 5)


def test_request_chart_returns_json_and_quotes_symbol(session):
    fake = session(FakeResponse(200, {"chart": {}}))
    assert request_chart("BRK-B", START, END) == {"chart": {}}
    url, kwargs = fake.calls[0]
    assert url.endswith("/v8/finance/chart/BRK-B")
    assert kwargs["params"]["interval"] == "1d"


@pytest.mark.parametrize(
    ("outcome", "expected", "message"),
    [
        (FakeResponse(404), SymbolNotFoundError, "查無資料"),
        (FakeResponse(429), DataSourceError, "限制查詢次數"),
        (FakeResponse(503), DataSourceError, "HTTP 503"),
        (FakeResponse(200, None), DataSourceError, "格式異常"),
        (
            OSError("curl: (60) SSL certificate problem"),
            DataSourceError,
            r"無法連線到 Yahoo：curl: \(60\)",
        ),
    ],
)
def test_request_chart_classifies_errors(session, outcome, expected, message):
    session(outcome)
    with pytest.raises(expected, match=message):
        request_chart("MSFT", START, END)
