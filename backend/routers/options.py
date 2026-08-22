import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import futu as ft
from futu_client import get_quote_ctx, us_symbol

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{ticker}/expirations")
def get_expirations(ticker: str):
    symbol = us_symbol(ticker)
    ctx = get_quote_ctx()
    try:
        ret, data = ctx.get_option_expiration_date(symbol)
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Expiry error: {data}")
        return {"symbol": ticker.upper(), "expirations": data["strike_time"].tolist()}
    finally:
        ctx.close()


@router.get("/{ticker}/chain")
def get_option_chain(
    ticker: str,
    expiry: str = Query(..., description="Expiration date YYYY-MM-DD"),
    option_type: Optional[str] = Query(None, description="call / put / all"),
    strike_min: Optional[float] = None,
    strike_max: Optional[float] = None,
):
    symbol = us_symbol(ticker)
    ctx = get_quote_ctx()
    try:
        ret, data = ctx.get_option_chain(
            code=symbol,
            index_option_type=ft.IndexOptionType.NORMAL,
            start=expiry,
            end=expiry,
        )
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Chain error: {data}")

        calls = []
        puts = []
        for _, row in data.iterrows():
            strike = float(row.get("strike_price", 0))
            if strike_min is not None and strike < strike_min:
                continue
            if strike_max is not None and strike > strike_max:
                continue

            otype = str(row.get("option_type", "")).upper()
            opt_code = str(row.get("code", ""))

            # Fetch live quote for each option
            snap_ret, snap = ctx.get_market_snapshot([opt_code])
            if snap_ret == ft.RET_OK and len(snap) > 0:
                s = snap.iloc[0]
                last = float(s.get("last_price", 0))
                bid = float(s.get("bid_price", 0))
                ask = float(s.get("ask_price", 0))
                volume = int(s.get("volume", 0))
                open_interest = int(s.get("open_interest", 0))
                iv = float(s.get("implied_volatility", 0))
                delta = float(s.get("delta", 0))
                gamma = float(s.get("gamma", 0))
                theta = float(s.get("theta", 0))
                vega = float(s.get("vega", 0))
                rho = float(s.get("rho", 0))
            else:
                last = bid = ask = iv = delta = gamma = theta = vega = rho = 0.0
                volume = open_interest = 0

            entry = {
                "code": opt_code,
                "strike": strike,
                "expiry": expiry,
                "last": last,
                "bid": bid,
                "ask": ask,
                "mid": round((bid + ask) / 2, 2) if bid and ask else last,
                "volume": volume,
                "open_interest": open_interest,
                "iv": iv,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "rho": rho,
            }
            if otype == "CALL":
                calls.append(entry)
            elif otype == "PUT":
                puts.append(entry)

        calls.sort(key=lambda x: x["strike"])
        puts.sort(key=lambda x: x["strike"])

        result = {"symbol": ticker.upper(), "expiry": expiry}
        if option_type == "call":
            result["calls"] = calls
        elif option_type == "put":
            result["puts"] = puts
        else:
            result["calls"] = calls
            result["puts"] = puts

        return result
    finally:
        ctx.close()


@router.get("/{ticker}/volatility")
def get_volatility(ticker: str):
    symbol = us_symbol(ticker)
    ctx = get_quote_ctx()
    try:
        ret, data = ctx.get_option_historical_volatility(symbol)
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Volatility error: {data}")
        records = []
        for _, row in data.iterrows():
            records.append({
                "time": str(row.get("time", "")),
                "iv": float(row.get("iv", 0)),
                "hv": float(row.get("hv", 0)),
            })
        return {"symbol": ticker.upper(), "data": records}
    finally:
        ctx.close()


@router.get("/screen")
def screen_options(
    market: str = "US",
    option_type: str = Query("call", description="call or put"),
    min_iv: Optional[float] = None,
    max_iv: Optional[float] = None,
    min_oi: Optional[int] = None,
    min_volume: Optional[int] = None,
    min_delta: Optional[float] = None,
    max_delta: Optional[float] = None,
    expiry_within_days: Optional[int] = None,
):
    ctx = get_quote_ctx()
    try:
        params = {
            "option_type": ft.OptionType.CALL if option_type == "call" else ft.OptionType.PUT,
        }
        if min_iv is not None:
            params["filter_list"] = []

        ret, data = ctx.get_option_filter(**params)
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Screen error: {data}")
        return {"results": data.to_dict(orient="records")}
    finally:
        ctx.close()
