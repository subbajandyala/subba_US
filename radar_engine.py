"""
Options Radar engine — pure analysis, no network calls.

Feed it raw MooMoo REST payload rows and it returns DataFrames:
  build_table()     option snapshots + underlying quotes (+ optional screener OI change) → one row per contract
  analyze()         adds buildup reading, buildup score and buyer-quality score
  underlying_bias() per-ticker call/put flow → BUY CALL / BUY PUT / NEUTRAL / LOW DATA
  pick_contracts()  best buyer-quality contract per signal
  track()           compare a saved scan with fresh snapshots → returns + hit rates

Logic ported from the India MarketPulse app:
  fo_scanner._score_stock                         → call/put bias score
  sensex_option_moves.run_oi_buildup_scanner      → Fresh (vol/OI), Stealth, Near-ATM tags
Adapted for US options: price moves are first adjusted for what delta + theta explain,
and 0-1 DTE contracts are tracked but excluded from direction (decay is too non-linear).
"""
import re
from datetime import datetime

import numpy as np
import pandas as pd

CODE_RE = re.compile(r"US\.([A-Z]+)(\d{6})([CP])(\d+)")

# Direction each buildup implies for the UNDERLYING
BIAS = {
    ("CALL", "Long buildup"): 1,     # call buyers
    ("CALL", "Short buildup"): -1,   # call writers → resistance
    ("PUT", "Long buildup"): -1,     # put buyers
    ("PUT", "Short buildup"): 1,     # put writers → support
    ("CALL", "Short covering"): 1,
    ("PUT", "Short covering"): -1,
}


def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def build_table(option_rows, underlying_rows, screen_rows=None):
    """option_rows: /quote/market_snapshot snapshot_list; underlying_rows: /quote/stock_quote quote_list;
    screen_rows: /quote/option_screen option_list (only source of the daily OI change)."""
    screen = {r.get("code"): r for r in (screen_rows or [])}
    und = {q.get("code"): q for q in underlying_rows}

    rows = []
    for s in option_rows:
        m = CODE_RE.match(str(s.get("code", "")))
        if not m:
            continue
        ticker = m.group(1)
        u = und.get("US." + ticker, {})
        bid, ask = _num(s.get("bid_price")), _num(s.get("ask_price"))
        last = _num(s.get("last_price"))
        rows.append({
            "code": s["code"],
            "ticker": ticker,
            "type": "CALL" if str(s.get("option_type")).upper() == "CALL" else "PUT",
            "strike": _num(s.get("option_strike_price")),
            "expiry": datetime.strptime(m.group(2), "%y%m%d").strftime("%Y-%m-%d"),
            "dte": int(_num(s.get("option_expiry_date_distance"))),
            "spot": _num(u.get("last_price")),
            "spot_prev": _num(u.get("prev_close_price")),
            "bid": bid,
            "ask": ask,
            "mid": round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else last,
            "last": last,
            "prev_close": _num(s.get("prev_close_price")),
            "volume": _num(s.get("volume")),
            "oi": _num(s.get("option_open_interest")),
            "oi_chg": _num(screen.get(s["code"], {}).get("oi_day_chg"), np.nan),
            "turnover": _num(s.get("turnover")),
            "iv": _num(s.get("option_implied_volatility")),
            "delta": _num(s.get("delta")),
            "gamma": _num(s.get("gamma")),
            "theta": _num(s.get("theta")),
            "vega": _num(s.get("vega")),
            "data_date": s.get("data_date"),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["px_chg_pct"] = np.where(df["prev_close"] > 0, (df["last"] - df["prev_close"]) / df["prev_close"] * 100, 0.0)
    df["spot_chg_pct"] = np.where(df["spot_prev"] > 0, (df["spot"] - df["spot_prev"]) / df["spot_prev"] * 100, 0.0)
    # Price the Greeks predict after the stock move + one day of decay; the rest is buying/selling pressure
    expected = (df["prev_close"] + df["delta"] * (df["spot"] - df["spot_prev"]) + df["theta"]).clip(lower=0.01)
    df["excess_pct"] = np.where(df["prev_close"] > 0, (df["last"] - expected) / df["prev_close"] * 100, 0.0)
    df["vol_oi"] = np.where(df["oi"] > 0, df["volume"] / df["oi"], 0.0)
    prior_oi = df["oi"] - df["oi_chg"].fillna(0)
    df["oi_add_pct"] = np.where(prior_oi > 0, df["oi_chg"] / prior_oi * 100,
                                np.where(df["oi_chg"] > 0, 999.0, 0.0))
    df["spread_pct"] = np.where(df["mid"] > 0, (df["ask"] - df["bid"]) / df["mid"] * 100, 999.0)
    df["theta_pct"] = np.where(df["mid"] > 0, df["theta"].abs() / df["mid"] * 100, 999.0)
    df["moneyness_pct"] = np.where(df["spot"] > 0, (df["strike"] - df["spot"]) / df["spot"] * 100, 0.0)
    return df


def classify_buildup(row):
    """OI up + price up = Long buildup; OI up + price down = Short buildup;
    OI down + price up = Short covering; OI down + price down = Long unwinding."""
    if row["dte"] <= 1:
        return "0-1 DTE (skip)"
    oi_chg, px = row["oi_chg"], row["excess_pct"]
    if pd.isna(oi_chg) or oi_chg == 0 or abs(px) < 3:
        return "—"
    if oi_chg > 0:
        return "Long buildup" if px > 0 else "Short buildup"
    return "Short covering" if px > 0 else "Long unwinding"


def buildup_score(row):
    score, tags = 0, []
    if row["vol_oi"] > 1.0:
        score += 2
        tags.append("Fresh (vol>OI)")
    elif row["vol_oi"] > 0.3:
        score += 1
    if row["oi_add_pct"] > 50:
        score += 2
        tags.append("OI added {:.0f}%".format(min(row["oi_add_pct"], 999)))
    elif row["oi_add_pct"] > 15:
        score += 1
    if row["volume"] > 20000 and abs(row["px_chg_pct"]) < 5:
        score += 2
        tags.append("Stealth")
    if abs(row["moneyness_pct"]) <= 2:
        score += 1
        tags.append("Near ATM")
    return score, ", ".join(tags) if tags else "—"


def buyer_quality(row):
    """0-100: how suitable the contract is for an option BUYER (Greeks + liquidity)."""
    s = 100.0
    d = abs(row["delta"])
    if d < 0.30 or d > 0.65:
        s -= 30
    s -= min(row["spread_pct"], 20) * 2.0
    s -= min(row["theta_pct"], 40) * 1.0
    if row["dte"] == 0:
        s -= 30
    elif row["dte"] > 21:
        s -= 10
    if row["oi"] < 1000:
        s -= 15
    return round(max(s, 0), 1)


def analyze(df):
    if df.empty:
        return df
    df = df.copy()
    df["buildup"] = df.apply(classify_buildup, axis=1)
    df["bias"] = [BIAS.get((t, b), 0) for t, b in zip(df["type"], df["buildup"])]
    sc = df.apply(buildup_score, axis=1, result_type="expand")
    df["buildup_score"] = sc[0].astype(int)
    df["buildup_tags"] = sc[1]
    df["buyer_q"] = df.apply(buyer_quality, axis=1)
    return df


def underlying_bias(df):
    out = []
    for t, g in df.groupby("ticker"):
        call_vol = g.loc[g["type"] == "CALL", "volume"].sum()
        put_vol = g.loc[g["type"] == "PUT", "volume"].sum()
        total = g["turnover"].sum()
        flow_pct = (g["bias"] * g["turnover"]).sum() / total * 100 if total else 0.0
        score = 0
        if flow_pct > 40:
            score += 2
        elif flow_pct > 15:
            score += 1
        elif flow_pct < -40:
            score -= 2
        elif flow_pct < -15:
            score -= 1
        both = call_vol > 0 and put_vol > 0
        pcr = put_vol / call_vol if call_vol else np.nan
        if both:
            if pcr < 0.6:
                score += 1
            elif pcr > 1.6:
                score -= 1
        if len(g) < 3 or not both:
            sig = "LOW DATA"
        elif score >= 3:
            sig = "STRONG BUY CALL"
        elif score >= 2:
            sig = "BUY CALL"
        elif score <= -3:
            sig = "STRONG BUY PUT"
        elif score <= -2:
            sig = "BUY PUT"
        else:
            sig = "NEUTRAL"
        out.append({
            "ticker": t, "spot": g["spot"].iloc[0], "spot_chg_pct": round(g["spot_chg_pct"].iloc[0], 2),
            "contracts": len(g), "call_vol": int(call_vol), "put_vol": int(put_vol),
            "pcr_vol": round(pcr, 2) if both else None, "flow_pct": round(flow_pct, 1),
            "score": score, "signal": sig, "premium_traded": round(total),
        })
    if not out:
        return pd.DataFrame()
    return pd.DataFrame(out).sort_values(["score", "premium_traded"], ascending=[False, False])


def pick_contracts(df, bias, per_signal=1):
    picks = []
    active = bias[~bias["signal"].isin(["NEUTRAL", "LOW DATA"])] if not bias.empty else bias
    for _, b in active.iterrows():
        want = "CALL" if "CALL" in b["signal"] else "PUT"
        c = df[(df["ticker"] == b["ticker"]) & (df["type"] == want) & (df["dte"] >= 1)]
        for _, r in c.sort_values("buyer_q", ascending=False).head(per_signal).iterrows():
            d = r.to_dict()
            d["signal"] = b["signal"]
            picks.append(d)
    return pd.DataFrame(picks)


def track(baseline, now):
    """baseline: a saved analyze() table; now: build_table() of fresh snapshots for the same codes."""
    m = baseline.merge(now[["code", "mid", "last", "spot", "bid", "ask"]], on="code", suffixes=("_then", "_now"))
    m["opt_ret_pct"] = np.where(m["mid_then"] > 0, (m["mid_now"] - m["mid_then"]) / m["mid_then"] * 100, np.nan)
    m["spot_ret_pct"] = np.where(m["spot_then"] > 0, (m["spot_now"] - m["spot_then"]) / m["spot_then"] * 100, np.nan)
    sw = m[m["dte"] >= 2].copy()
    sw["implied_dir"] = [BIAS.get((t, b), 0) for t, b in zip(sw["type"], sw["buildup"])]
    sw = sw[sw["implied_dir"] != 0]
    if sw.empty:
        hit = pd.DataFrame()
    else:
        sw["dir_right"] = np.sign(sw["spot_ret_pct"]) == sw["implied_dir"]
        hit = (sw.groupby(["type", "buildup"])
                 .agg(contracts=("code", "size"), direction_hit_rate=("dir_right", "mean"),
                      avg_option_return_pct=("opt_ret_pct", "mean"))
                 .round(2).reset_index())
    return m, hit
