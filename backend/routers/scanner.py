"""
Options Scanner — scan a list of tickers for OI signals in one call.
Returns results sorted by signal strength (abs score).
"""
import logging
from fastapi import APIRouter, Query
import futu as ft
from futu_client import get_quote_ctx, us_symbol
from routers.analysis import _calc_pcr, _calc_max_pain, _score_signal

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_TICKERS = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,SPY,QQQ,IWM,JPM,NFLX,AVGO,CRM"


@router.get("/scan")
def oi_scan(
    tickers: str = Query(DEFAULT_TICKERS, description="Comma-separated tickers"),
    expiry_offset: int = Query(0, description="Expiry index: 0=nearest, 1=next"),
):
    """Scan multiple tickers for their OI signal (nearest expiry by default)."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    results = []

    ctx = get_quote_ctx()
    try:
        for ticker in ticker_list:
            symbol = us_symbol(ticker)
            try:
                ret, snap = ctx.get_market_snapshot([symbol])
                if ret != ft.RET_OK:
                    continue
                spot = float(snap.iloc[0].get("last_price", 0))

                ret_e, exp_df = ctx.get_option_expiration_date(code=symbol)
                if ret_e != ft.RET_OK or len(exp_df) <= expiry_offset:
                    continue
                expiry = str(exp_df.iloc[expiry_offset]["time"])[:10]

                ret2, chain_df = ctx.get_option_chain(
                    code=symbol,
                    index_option_type=ft.IndexOptionType.NORMAL,
                    start=expiry,
                    end=expiry,
                )
                if ret2 != ft.RET_OK:
                    continue

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
                            "open_interest": int(s.get("open_interest", 0)),
                            "volume": int(s.get("volume", 0)),
                        })

                if not chain_rows:
                    continue

                pcr = _calc_pcr(chain_rows)
                max_pain = _calc_max_pain(chain_rows)
                sig = _score_signal(chain_rows, spot, pcr, max_pain)
                mp_dist = round((spot - max_pain) / max_pain * 100, 2) if max_pain else 0

                results.append({
                    "ticker": ticker,
                    "spot": spot,
                    "expiry": expiry,
                    "pcr": pcr,
                    "max_pain": max_pain,
                    "mp_dist_pct": mp_dist,
                    "signal": sig["signal"],
                    "score": sig["score"],
                    "max_call_wall": sig.get("max_call_wall", 0),
                    "max_put_wall": sig.get("max_put_wall", 0),
                })
            except Exception as e:
                logger.warning("Scan %s: %s", ticker, e)

    finally:
        ctx.close()

    results.sort(key=lambda x: abs(x["score"]), reverse=True)
    return {"results": results, "scanned": len(ticker_list), "returned": len(results)}
