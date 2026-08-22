import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import futu as ft
from futu_client import get_trade_ctx, us_symbol, TRADE_ENV

router = APIRouter()
logger = logging.getLogger(__name__)


class OrderRequest(BaseModel):
    ticker: str
    qty: float
    price: float
    side: str          # BUY or SELL
    order_type: str = "NORMAL"  # NORMAL (limit) | MARKET | STOP | STOP_LIMIT
    stop_price: Optional[float] = None
    remark: Optional[str] = None


class CancelRequest(BaseModel):
    order_id: str


def _open_trade():
    ctx = get_trade_ctx()
    pwd = os.getenv("TRADE_UNLOCK_PWD", "")
    if pwd and TRADE_ENV == ft.TrdEnv.REAL:
        ret, data = ctx.unlock_trade(pwd)
        if ret != ft.RET_OK:
            ctx.close()
            raise HTTPException(status_code=403, detail=f"Trade unlock failed: {data}")
    return ctx


ORDER_TYPE_MAP = {
    "NORMAL": ft.OrderType.NORMAL,
    "MARKET": ft.OrderType.MARKET,
    "STOP": ft.OrderType.STOP,
    "STOP_LIMIT": ft.OrderType.STOP_LIMIT,
    "AUCTION": ft.OrderType.AUCTION,
}

SIDE_MAP = {
    "BUY": ft.TrdSide.BUY,
    "SELL": ft.TrdSide.SELL,
    "SELL_SHORT": ft.TrdSide.SELL_SHORT,
    "BUY_BACK": ft.TrdSide.BUY_BACK,
}


@router.post("/order")
def place_order(req: OrderRequest):
    symbol = us_symbol(req.ticker)
    trd_side = SIDE_MAP.get(req.side.upper(), ft.TrdSide.BUY)
    order_type = ORDER_TYPE_MAP.get(req.order_type.upper(), ft.OrderType.NORMAL)

    ctx = _open_trade()
    try:
        kwargs = dict(
            price=req.price,
            qty=req.qty,
            code=symbol,
            trd_side=trd_side,
            order_type=order_type,
            trd_env=TRADE_ENV,
        )
        if req.remark:
            kwargs["remark"] = req.remark

        ret, data = ctx.place_order(**kwargs)
        if ret != ft.RET_OK:
            raise HTTPException(status_code=400, detail=f"Place order error: {data}")
        return {
            "success": True,
            "order_id": str(data["order_id"].iloc[0]),
            "env": str(TRADE_ENV),
        }
    finally:
        ctx.close()


@router.post("/order/cancel")
def cancel_order(req: CancelRequest):
    ctx = _open_trade()
    try:
        ret, data = ctx.modify_order(
            modify_order_op=ft.ModifyOrderOp.CANCEL,
            order_id=req.order_id,
            qty=0,
            price=0,
            trd_env=TRADE_ENV,
        )
        if ret != ft.RET_OK:
            raise HTTPException(status_code=400, detail=f"Cancel error: {data}")
        return {"success": True, "order_id": req.order_id}
    finally:
        ctx.close()


@router.get("/max-qty/{ticker}")
def get_max_qty(ticker: str, price: float, side: str = "BUY"):
    symbol = us_symbol(ticker)
    trd_side = SIDE_MAP.get(side.upper(), ft.TrdSide.BUY)
    ctx = _open_trade()
    try:
        ret, data = ctx.acctradinginfo_query(
            order_type=ft.OrderType.NORMAL,
            code=symbol,
            price=price,
            order_side=trd_side,
            trd_env=TRADE_ENV,
        )
        if ret != ft.RET_OK:
            raise HTTPException(status_code=400, detail=f"Max qty error: {data}")
        row = data.iloc[0]
        return {
            "max_cash_buy": float(row.get("max_cash_buy", 0)),
            "max_cash_and_margin_buy": float(row.get("max_cash_and_margin_buy", 0)),
            "max_position_sell": float(row.get("max_position_sell", 0)),
            "max_sell_short": float(row.get("max_sell_short", 0)),
            "long_required_im": float(row.get("long_required_im", 0)),
        }
    finally:
        ctx.close()
