import logging
import os
from fastapi import APIRouter, HTTPException
import futu as ft
from futu_client import get_trade_ctx, TRADE_ENV

router = APIRouter()
logger = logging.getLogger(__name__)


def _open_trade():
    ctx = get_trade_ctx()
    # Unlock trade if password provided
    pwd = os.getenv("TRADE_UNLOCK_PWD", "")
    if pwd and TRADE_ENV == ft.TrdEnv.REAL:
        ret, data = ctx.unlock_trade(pwd)
        if ret != ft.RET_OK:
            ctx.close()
            raise HTTPException(status_code=403, detail=f"Trade unlock failed: {data}")
    return ctx


@router.get("/positions")
def get_positions():
    ctx = _open_trade()
    try:
        ret, data = ctx.position_list_query(trd_env=TRADE_ENV)
        if ret != ft.RET_OK:
            raise HTTPException(status_code=500, detail=f"Positions error: {data}")
        positions = []
        for _, row in data.iterrows():
            positions.append({
                "code": str(row.get("code", "")),
                "name": str(row.get("stock_name", "")),
                "qty": float(row.get("qty", 0)),
                "can_sell_qty": float(row.get("can_sell_qty", 0)),
                "cost_price": float(row.get("cost_price", 0)),
                "market_val": float(row.get("market_val", 0)),
                "nominal_price": float(row.get("nominal_price", 0)),
                "unrealized_pl": float(row.get("unrealized_pl", 0)),
                "unrealized_pl_ratio": float(row.get("unrealized_pl_ratio", 0)),
                "realized_pl": float(row.get("realized_pl", 0)),
                "currency": str(row.get("currency", "USD")),
                "position_side": str(row.get("position_side", "")),
            })
        return {"positions": positions, "env": str(TRADE_ENV)}
    finally:
        ctx.close()


@router.get("/orders")
def get_orders(status: str = "active"):
    ctx = _open_trade()
    try:
        if status == "active":
            ret, data = ctx.order_list_query(trd_env=TRADE_ENV)
        else:
            ret, data = ctx.history_order_list_query(
                status_filter_list=[
                    ft.OrderStatus.FILLED_ALL,
                    ft.OrderStatus.CANCELLED_ALL,
                    ft.OrderStatus.FAILED,
                ],
                trd_env=TRADE_ENV,
            )
        if ret != ft.RET_OK:
            raise HTTPException(status_code=500, detail=f"Orders error: {data}")
        orders = []
        for _, row in data.iterrows():
            orders.append({
                "order_id": str(row.get("order_id", "")),
                "code": str(row.get("code", "")),
                "name": str(row.get("stock_name", "")),
                "qty": float(row.get("qty", 0)),
                "price": float(row.get("price", 0)),
                "trd_side": str(row.get("trd_side", "")),
                "order_type": str(row.get("order_type", "")),
                "order_status": str(row.get("order_status", "")),
                "dealt_qty": float(row.get("dealt_qty", 0)),
                "dealt_avg_price": float(row.get("dealt_avg_price", 0)),
                "create_time": str(row.get("create_time", "")),
                "updated_time": str(row.get("updated_time", "")),
            })
        return {"orders": orders, "env": str(TRADE_ENV)}
    finally:
        ctx.close()


@router.get("/funds")
def get_funds():
    ctx = _open_trade()
    try:
        ret, data = ctx.accinfo_query(trd_env=TRADE_ENV)
        if ret != ft.RET_OK:
            raise HTTPException(status_code=500, detail=f"Funds error: {data}")
        row = data.iloc[0]
        return {
            "power": float(row.get("power", 0)),
            "total_assets": float(row.get("total_assets", 0)),
            "cash": float(row.get("cash", 0)),
            "market_val": float(row.get("market_val", 0)),
            "frozen_cash": float(row.get("frozen_cash", 0)),
            "unrealized_pl": float(row.get("unrealized_pl", 0)),
            "realized_pl": float(row.get("realized_pl", 0)),
            "currency": "USD",
            "env": str(TRADE_ENV),
        }
    finally:
        ctx.close()
