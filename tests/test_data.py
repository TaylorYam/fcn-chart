from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from fcn_chart.data import drop_unfinished_bar, to_candles

NY = "America/New_York"
TOKYO = "Asia/Tokyo"


def make_df(dates, tz):
    index = pd.DatetimeIndex([pd.Timestamp(d, tz=tz) for d in dates])
    n = len(dates)
    return pd.DataFrame(
        {"Open": [1.0] * n, "High": [2.0] * n, "Low": [0.5] * n, "Close": range(10, 10 + n)},
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
