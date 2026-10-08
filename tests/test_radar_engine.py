"""Offline checks for radar_engine using small synthetic MooMoo-shaped payloads."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import radar_engine as re_  # noqa: E402


def _opt(code, otype, strike, dte, bid, ask, last, prev, vol, oi, delta, theta, turnover=1e6):
    return {"code": code, "option_type": otype, "option_strike_price": strike,
            "option_expiry_date_distance": dte, "bid_price": bid, "ask_price": ask,
            "last_price": last, "prev_close_price": prev, "volume": vol,
            "option_open_interest": oi, "turnover": turnover, "option_implied_volatility": 20,
            "delta": delta, "gamma": 0.05, "theta": theta, "vega": 0.1, "data_date": "2026-10-07"}


UND = [{"code": "US.XYZ", "last_price": 100.0, "prev_close_price": 100.0}]


def test_long_buildup_call_is_bullish():
    # OI up, price well above what delta/theta explain → call buyers
    opts = [_opt("US.XYZ261016C100000", "CALL", 100, 8, 2.9, 3.1, 3.0, 2.0, 50000, 20000, 0.5, -0.1),
            _opt("US.XYZ261016P100000", "PUT", 100, 8, 1.9, 2.1, 2.0, 2.0, 5000, 20000, -0.5, -0.1),
            _opt("US.XYZ261016C105000", "CALL", 105, 8, 0.9, 1.1, 1.5, 1.0, 30000, 10000, 0.3, -0.05)]
    screen = [{"code": "US.XYZ261016C100000", "oi_day_chg": "15000"},
              {"code": "US.XYZ261016C105000", "oi_day_chg": "8000"}]
    df = re_.analyze(re_.build_table(opts, UND, screen))
    row = df.set_index("code").loc["US.XYZ261016C100000"]
    assert row["buildup"] == "Long buildup"
    bias = re_.underlying_bias(df)
    assert bias.iloc[0]["signal"] in ("BUY CALL", "STRONG BUY CALL")
    picks = re_.pick_contracts(df, bias)
    assert picks.iloc[0]["type"] == "CALL"


def test_zero_dte_excluded_from_direction():
    opts = [_opt("US.XYZ261008C100000", "CALL", 100, 0, 0.9, 1.0, 1.0, 3.0, 90000, 10000, 0.5, -2.5)]
    screen = [{"code": "US.XYZ261008C100000", "oi_day_chg": "9000"}]
    df = re_.analyze(re_.build_table(opts, UND, screen))
    assert df.iloc[0]["buildup"] == "0-1 DTE (skip)"
    assert df.iloc[0]["bias"] == 0


def test_one_sided_ticker_is_low_data():
    opts = [_opt("US.XYZ261016C100000", "CALL", 100, 8, 2.9, 3.1, 3.0, 2.0, 50000, 20000, 0.5, -0.1)]
    df = re_.analyze(re_.build_table(opts, UND, [{"code": "US.XYZ261016C100000", "oi_day_chg": "15000"}]))
    assert re_.underlying_bias(df).iloc[0]["signal"] == "LOW DATA"


def test_track_returns():
    opts = [_opt("US.XYZ261016C100000", "CALL", 100, 8, 2.9, 3.1, 3.0, 2.0, 50000, 20000, 0.5, -0.1)]
    base = re_.analyze(re_.build_table(opts, UND, [{"code": "US.XYZ261016C100000", "oi_day_chg": "15000"}]))
    later = [_opt("US.XYZ261016C100000", "CALL", 100, 7, 3.9, 4.1, 4.0, 3.0, 1000, 35000, 0.6, -0.1)]
    now = re_.build_table(later, [{"code": "US.XYZ", "last_price": 102.0, "prev_close_price": 100.0}])
    m, hit = re_.track(base, now)
    assert round(m.iloc[0]["opt_ret_pct"]) == 33
    assert hit.iloc[0]["direction_hit_rate"] == 1.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
