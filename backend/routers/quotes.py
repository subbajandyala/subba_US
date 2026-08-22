import logging
from fastapi import APIRouter, HTTPException
import futu as ft
from futu_client import get_quote_ctx, us_symbol

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{ticker}")
def get_quote(ticker: str):
    symbol = us_symbol(ticker)
    ctx = get_quote_ctx()
    try:
        ret, data = ctx.get_market_snapshot([symbol])
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"Quote error: {data}")

        row = data.iloc[0]
        return {
            "symbol": ticker.upper(),
            "name": row.get("stock_name", ""),
            "last_price": float(row.get("last_price", 0)),
            "open": float(row.get("open_price", 0)),
            "high": float(row.get("high_price", 0)),
            "low": float(row.get("low_price", 0)),
            "prev_close": float(row.get("prev_close_price", 0)),
            "change": float(row.get("change_val", 0)),
            "change_pct": float(row.get("change_rate", 0)),
            "volume": int(row.get("volume", 0)),
            "turnover": float(row.get("turnover", 0)),
            "market_cap": float(row.get("market_cap", 0)),
            "pe_ratio": float(row.get("pe_ratio", 0) or 0),
            "week52_high": float(row.get("wk52_high_price", 0)),
            "week52_low": float(row.get("wk52_low_price", 0)),
            "lot_size": int(row.get("lot_size", 100)),
        }
    finally:
        ctx.close()


@router.get("/{ticker}/kline")
def get_kline(ticker: str, period: str = "day", count: int = 60):
    ktype_map = {
        "1min": ft.KLType.K_1M,
        "5min": ft.KLType.K_5M,
        "15min": ft.KLType.K_15M,
        "30min": ft.KLType.K_30M,
        "60min": ft.KLType.K_60M,
        "day": ft.KLType.K_DAY,
        "week": ft.KLType.K_WEEK,
    }
    ktype = ktype_map.get(period, ft.KLType.K_DAY)
    symbol = us_symbol(ticker)
    ctx = get_quote_ctx()
    try:
        ret, data, _ = ctx.get_cur_kline(symbol, count, ktype)
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"KLine error: {data}")
        records = []
        for _, row in data.iterrows():
            records.append({
                "time": str(row["time_key"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            })
        return records
    finally:
        ctx.close()


@router.get("/{ticker}/orderbook")
def get_orderbook(ticker: str):
    symbol = us_symbol(ticker)
    ctx = get_quote_ctx()
    try:
        ret, data = ctx.get_order_book(symbol, num=10)
        if ret != ft.RET_OK:
            raise HTTPException(status_code=404, detail=f"OrderBook error: {data}")
        return {
            "bids": [{"price": float(p), "volume": int(v), "order_num": int(n)} for p, v, n in data.get("Bid", [])],
            "asks": [{"price": float(p), "volume": int(v), "order_num": int(n)} for p, v, n in data.get("Ask", [])],
        }
    finally:
        ctx.close()
