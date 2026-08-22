"""
OI Signal Analysis — PCR, Max Pain, OI Walls → BUY CALL/PUT signal.
Ported from the India MarketPulse app, adapted for US options via futu-api.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import futu as ft
import numpy as np
from futu_client import get_quote_ctx, us_symbol

router = APIRouter()
logger = logging.getLogger(__name__)


def _calc_pcr(chain_rows: list[dict]) -> float:
    total_ce = sum(r.get("open_interest", 0) for r in chain_rows if r.get("option_type") == "CALL")
    total_pe = sum(r.get("open_interest", 0) for r in chain_rows if r.get("option_type") == "PUT")
    return round(total_pe / total_ce, 4) if total_ce > 0 else 0.0


def _calc_max_pain(chain_rows: list[dict]) -> float:
    strikes = sorted(set(r["strike"] for r in chain_rows))
    if not strikes:
        return 0.0
    by_strike: dict[float, dict] = {}
    for r in chain_rows:
        s = r["strike"]
        if s not in by_strike:
            by_strike[s] = {"ce_oi": 0, "pe_oi": 0}
        if r.get("option_type") == "CALL":
            by_strike[s]["ce_oi"] += r.get("open_interest", 0)
        else:
            by_strike[s]["pe_oi"] += r.get("open_interest", 0)

    min_pain = float("inf")
    max_pain_strike = strikes[0]
    for test_strike in strikes:
        pain = 0.0
        for s, v in by_strike.items():
            # CE writers lose if spot > strike
            if test_strike > s:
                pain += v["ce_oi"] * (test_strike - s)
            # PE writers lose if spot < strike
            if test_strike < s:
                pain += v["pe_oi"] * (s - test_strike)
        if pain < min_pain:
            min_pain = pain
            max_pain_strike = test_strike
    return max_pain_strike


def _score_signal(chain_rows: list[dict], spot: float, pcr: float, max_pain: float) -> dict:
    """
    Composite OI score → BUY CALL / BUY PUT / NEUTRAL signal.
    Positive score = bullish (BUY CALL), negative = bearish (BUY PUT).
    """
    score = 0
    details = []

    # ── 1. PCR ──────────────────────────────────────────────────────────────────
    if pcr >= 1.3:
        score += 2
        details.append({"indicator": "PCR", "value": f"{pcr:.2f}",
                         "verdict": "Bullish 🟢",
                         "explanation": "Heavy put writing = strong support floor"})
    elif pcr >= 1.0:
        score += 1
        details.append({"indicator": "PCR", "value": f"{pcr:.2f}",
                         "verdict": "Mildly Bullish 🟡", "explanation": "More puts than calls = mild support"})
    elif pcr <= 0.7:
        score -= 2
        details.append({"indicator": "PCR", "value": f"{pcr:.2f}",
                         "verdict": "Bearish 🔴", "explanation": "Heavy call writing = strong resistance"})
    elif pcr < 1.0:
        score -= 1
        details.append({"indicator": "PCR", "value": f"{pcr:.2f}",
                         "verdict": "Mildly Bearish 🟡", "explanation": "More calls than puts = mild resistance"})
    else:
        details.append({"indicator": "PCR", "value": f"{pcr:.2f}",
                         "verdict": "Neutral ⚪", "explanation": "Balanced call/put OI"})

    # ── 2. Max Pain vs Spot ──────────────────────────────────────────────────────
    mp_diff_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0
    if mp_diff_pct > 1.0:
        score -= 2
        details.append({"indicator": "Max Pain", "value": f"Spot {spot:.2f}  MP {max_pain:.2f}  (+{mp_diff_pct:.1f}%)",
                         "verdict": "Bearish 🔴", "explanation": "Spot well above Max Pain — gravity pulls price down"})
    elif mp_diff_pct > 0.3:
        score -= 1
        details.append({"indicator": "Max Pain", "value": f"Spot {spot:.2f}  MP {max_pain:.2f}  (+{mp_diff_pct:.1f}%)",
                         "verdict": "Mildly Bearish 🟡", "explanation": "Spot slightly above Max Pain"})
    elif mp_diff_pct < -1.0:
        score += 2
        details.append({"indicator": "Max Pain", "value": f"Spot {spot:.2f}  MP {max_pain:.2f}  ({mp_diff_pct:.1f}%)",
                         "verdict": "Bullish 🟢", "explanation": "Spot well below Max Pain — gravity pulls price up"})
    elif mp_diff_pct < -0.3:
        score += 1
        details.append({"indicator": "Max Pain", "value": f"Spot {spot:.2f}  MP {max_pain:.2f}  ({mp_diff_pct:.1f}%)",
                         "verdict": "Mildly Bullish 🟡", "explanation": "Spot slightly below Max Pain"})
    else:
        details.append({"indicator": "Max Pain", "value": f"Spot ≈ MP {max_pain:.2f}  ({mp_diff_pct:.1f}%)",
                         "verdict": "Neutral ⚪", "explanation": "Spot near Max Pain — range-bound"})

    # ── 3. CE OI Wall (above ATM) ─────────────────────────────────────────────
    calls = sorted([r for r in chain_rows if r.get("option_type") == "CALL"], key=lambda x: x["strike"])
    puts  = sorted([r for r in chain_rows if r.get("option_type") == "PUT"],  key=lambda x: x["strike"])

    max_ce_oi = max((r.get("open_interest", 0) for r in calls), default=0)
    max_pe_oi = max((r.get("open_interest", 0) for r in puts),  default=0)
    max_ce_strike = next((r["strike"] for r in calls if r.get("open_interest", 0) == max_ce_oi), 0)
    max_pe_strike = next((r["strike"] for r in puts  if r.get("open_interest", 0) == max_pe_oi), 0)

    if spot > max_ce_strike and max_ce_strike > 0:
        score += 1
        details.append({"indicator": "Key OI Levels",
                         "value": f"Spot {spot:.2f} > CE wall {max_ce_strike:.2f}",
                         "verdict": "Bullish 🟢", "explanation": "Spot broke above highest call OI — resistance cleared"})
    elif spot < max_pe_strike and max_pe_strike > 0:
        score -= 1
        details.append({"indicator": "Key OI Levels",
                         "value": f"Spot {spot:.2f} < PE wall {max_pe_strike:.2f}",
                         "verdict": "Bearish 🔴", "explanation": "Spot below highest put OI — support broken"})
    else:
        details.append({"indicator": "Key OI Levels",
                         "value": f"Resistance ${max_ce_strike:.2f}  |  Support ${max_pe_strike:.2f}",
                         "verdict": "Neutral ⚪",
                         "explanation": f"Spot {spot:.2f} between key OI walls"})

    # ── Final verdict ──────────────────────────────────────────────────────────
    if   score >=  4: signal = "STRONG BUY CALL 📈"
    elif score >=  2: signal = "BUY CALL 📈"
    elif score <= -4: signal = "STRONG BUY PUT 📉"
    elif score <= -2: signal = "BUY PUT 📉"
    else:             signal = "NEUTRAL — WAIT ⚖️"

    return {
        "signal": signal,
        "score": score,
        "details": details,
        "max_call_wall": max_ce_strike,
        "max_put_wall": max_pe_strike,
    }


def _recommend_trade(signal: str, score: int, chain_rows: list[dict],
                     atm: float, expiry: str) -> dict:
    strikes = sorted(set(r["strike"] for r in chain_rows))
    gaps = [b - a for a, b in zip(strikes, strikes[1:])] if len(strikes) > 1 else [1.0]
    gap = min(gaps)

    is_neutral = "NEUTRAL" in signal
    is_call    = "CALL" in signal
    is_strong  = "STRONG" in signal

    if is_neutral:
        atm_calls = [r for r in chain_rows if r.get("option_type") == "CALL" and abs(r["strike"] - atm) < gap * 0.6]
        atm_puts  = [r for r in chain_rows if r.get("option_type") == "PUT"  and abs(r["strike"] - atm) < gap * 0.6]
        return {
            "neutral": True,
            "atm": atm,
            "call_ltp": atm_calls[0].get("last", 0) if atm_calls else 0,
            "put_ltp":  atm_puts[0].get("last",  0) if atm_puts  else 0,
            "expiry": expiry,
            "score": score,
        }

    rec_strike = atm if is_strong else (atm + gap if is_call else atm - gap)
    target_rows = [r for r in chain_rows
                   if r.get("option_type") == ("CALL" if is_call else "PUT")
                   and abs(r["strike"] - rec_strike) < gap * 0.6]
    if not target_rows:
        target_rows = [r for r in chain_rows
                       if r.get("option_type") == ("CALL" if is_call else "PUT")
                       and abs(r["strike"] - atm) < gap * 0.6]

    ltp = target_rows[0].get("last", 0) if target_rows else 0
    actual_strike = target_rows[0]["strike"] if target_rows else rec_strike

    if ltp < 0.01 and not is_strong:
        # fallback to ATM
        atm_rows = [r for r in chain_rows
                    if r.get("option_type") == ("CALL" if is_call else "PUT")
                    and abs(r["strike"] - atm) < gap * 0.6]
        if atm_rows:
            ltp = atm_rows[0].get("last", 0)
            actual_strike = atm

    sl     = round(ltp * 0.65, 2)
    target = round(ltp * 1.65, 2)
    rr     = round((target - ltp) / (ltp - sl), 1) if ltp > sl else 0

    return {
        "neutral": False,
        "strike": actual_strike,
        "type": "CALL" if is_call else "PUT",
        "ltp": ltp,
        "expiry": expiry,
        "sl": sl,
        "target": target,
        "rr": rr,
        "strong": is_strong,
        "score": score,
    }


@router.get("/{ticker}/oi-signal")
def get_oi_signal(
    ticker: str,
    expiry: str = Query(..., description="Expiration date YYYY-MM-DD"),
    strikes_atm: int = Query(10, description="Strikes ± ATM to show"),
):
    symbol = us_symbol(ticker)
    ctx = get_quote_ctx()
    try:
        # Get spot
        ret, snap = ctx.get_market_snapshot([symbol])
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Quote error: {snap}")
        spot = float(snap.iloc[0].get("last_price", 0))

        # Get option chain
        ret2, chain_df = ctx.get_option_chain(
            code=symbol,
            index_option_type=ft.IndexOptionType.NORMAL,
            start=expiry,
            end=expiry,
        )
        if ret2 != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Chain error: {chain_df}")

        # Collect codes to batch-fetch quotes
        codes = chain_df["code"].tolist()
        chain_rows = []
        for code in codes:
            row_df = chain_df[chain_df["code"] == code].iloc[0]
            strike = float(row_df.get("strike_price", 0))
            otype  = str(row_df.get("option_type", "")).upper()
            # Fetch live quote
            sr, sd = ctx.get_market_snapshot([str(code)])
            if sr == ft.RET_OK and len(sd) > 0:
                s = sd.iloc[0]
                chain_rows.append({
                    "code": str(code),
                    "strike": strike,
                    "option_type": "CALL" if "CALL" in otype else "PUT",
                    "last": float(s.get("last_price", 0)),
                    "bid":  float(s.get("bid_price",  0)),
                    "ask":  float(s.get("ask_price",  0)),
                    "open_interest": int(s.get("open_interest", 0)),
                    "volume": int(s.get("volume", 0)),
                    "iv": float(s.get("implied_volatility", 0)),
                    "delta": float(s.get("delta", 0)),
                })

        # Find ATM
        all_strikes = sorted(set(r["strike"] for r in chain_rows))
        atm = min(all_strikes, key=lambda x: abs(x - spot)) if all_strikes else spot

        # Compute analytics
        pcr      = _calc_pcr(chain_rows)
        max_pain = _calc_max_pain(chain_rows)
        sig_data = _score_signal(chain_rows, spot, pcr, max_pain)
        trade    = _recommend_trade(sig_data["signal"], sig_data["score"], chain_rows, atm, expiry)

        # Filter near-ATM rows for display
        atm_idx = all_strikes.index(atm) if atm in all_strikes else 0
        lo = max(0, atm_idx - strikes_atm)
        hi = min(len(all_strikes), atm_idx + strikes_atm + 1)
        visible_strikes = set(all_strikes[lo:hi])

        calls_disp = sorted([r for r in chain_rows if r["option_type"] == "CALL" and r["strike"] in visible_strikes], key=lambda x: x["strike"])
        puts_disp  = sorted([r for r in chain_rows if r["option_type"] == "PUT"  and r["strike"] in visible_strikes], key=lambda x: x["strike"])

        total_ce_oi = sum(r.get("open_interest", 0) for r in chain_rows if r["option_type"] == "CALL")
        total_pe_oi = sum(r.get("open_interest", 0) for r in chain_rows if r["option_type"] == "PUT")

        return {
            "ticker": ticker.upper(),
            "spot": spot,
            "atm": atm,
            "expiry": expiry,
            "pcr": pcr,
            "max_pain": max_pain,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            **sig_data,
            "trade": trade,
            "calls": calls_disp,
            "puts": puts_disp,
        }
    finally:
        ctx.close()
