"""
Expiry Day Analyzer — nearest-expiry OI analysis for SPY/QQQ/any ticker.
Highlights "expiry rocket" conditions where spot is far from Max Pain.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
import futu as ft
from futu_client import get_quote_ctx, us_symbol
from routers.analysis import _calc_pcr, _calc_max_pain, _score_signal

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/analyze")
def expiry_analyze(
    ticker: str = Query("SPY"),
    expiry_offset: int = Query(0, description="0=nearest expiry, 1=next, …"),
):
    symbol = us_symbol(ticker)
    ctx = get_quote_ctx()
    try:
        # Spot price
        ret, snap = ctx.get_market_snapshot([symbol])
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Quote error: {snap}")
        spot = float(snap.iloc[0].get("last_price", 0))

        # Expirations
        ret_e, exp_df = ctx.get_option_expiration_date(code=symbol)
        if ret_e != ft.RET_OK or len(exp_df) <= expiry_offset:
            raise HTTPException(status_code=404, detail="No expiration dates found")
        expiry = str(exp_df.iloc[expiry_offset]["time"])[:10]

        # Full chain
        ret2, chain_df = ctx.get_option_chain(
            code=symbol,
            index_option_type=ft.IndexOptionType.NORMAL,
            start=expiry,
            end=expiry,
        )
        if ret2 != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Chain error: {chain_df}")

        chain_rows = []
        for code in chain_df["code"].tolist():
            row_df = chain_df[chain_df["code"] == code].iloc[0]
            strike = float(row_df.get("strike_price", 0))
            otype = str(row_df.get("option_type", "")).upper()
            sr, sd = ctx.get_market_snapshot([str(code)])
            if sr == ft.RET_OK and len(sd) > 0:
                s = sd.iloc[0]
                chain_rows.append({
                    "strike": strike,
                    "option_type": "CALL" if "CALL" in otype else "PUT",
                    "last": float(s.get("last_price", 0)),
                    "open_interest": int(s.get("open_interest", 0)),
                    "volume": int(s.get("volume", 0)),
                    "iv": float(s.get("implied_volatility", 0)),
                })

        if not chain_rows:
            raise HTTPException(status_code=404, detail="No option data returned")

        pcr = _calc_pcr(chain_rows)
        max_pain = _calc_max_pain(chain_rows)
        sig = _score_signal(chain_rows, spot, pcr, max_pain)

        mp_dist_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0

        # Expiry rocket conditions
        rocket_up = mp_dist_pct < -1.5 and pcr > 1.1
        rocket_dn = mp_dist_pct > 1.5 and pcr < 0.9

        # OI distribution for chart
        from collections import defaultdict
        by_strike: dict[float, dict] = defaultdict(lambda: {"ce_oi": 0, "pe_oi": 0})
        for r in chain_rows:
            if r["option_type"] == "CALL":
                by_strike[r["strike"]]["ce_oi"] += r["open_interest"]
            else:
                by_strike[r["strike"]]["pe_oi"] += r["open_interest"]

        all_strikes = sorted(set(r["strike"] for r in chain_rows))
        atm = min(all_strikes, key=lambda x: abs(x - spot)) if all_strikes else spot
        atm_idx = all_strikes.index(atm) if atm in all_strikes else 0
        lo = max(0, atm_idx - 10)
        hi = min(len(all_strikes), atm_idx + 11)
        oi_chart = [
            {"strike": s, "CE": by_strike[s]["ce_oi"], "PE": by_strike[s]["pe_oi"]}
            for s in all_strikes[lo:hi]
        ]

        return {
            "ticker": ticker.upper(),
            "expiry": expiry,
            "spot": spot,
            "atm": atm,
            "max_pain": max_pain,
            "pcr": pcr,
            "mp_dist_pct": round(mp_dist_pct, 2),
            "rocket_up": rocket_up,
            "rocket_down": rocket_dn,
            "signal": sig["signal"],
            "score": sig["score"],
            "details": sig["details"],
            "max_call_wall": sig.get("max_call_wall", 0),
            "max_put_wall": sig.get("max_put_wall", 0),
            "total_ce_oi": sum(r["open_interest"] for r in chain_rows if r["option_type"] == "CALL"),
            "total_pe_oi": sum(r["open_interest"] for r in chain_rows if r["option_type"] == "PUT"),
            "oi_chart": oi_chart,
        }
    finally:
        ctx.close()
