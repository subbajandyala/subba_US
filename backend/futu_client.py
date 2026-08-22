"""Singleton Futu/MooMoo client manager."""
import os
import logging
import futu as ft

logger = logging.getLogger(__name__)

FUTU_HOST = os.getenv("FUTU_HOST", "127.0.0.1")
FUTU_PORT = int(os.getenv("FUTU_PORT", "11111"))
TRADE_ENV = ft.TrdEnv.PAPER if os.getenv("TRADE_ENV", "PAPER") == "PAPER" else ft.TrdEnv.REAL


def get_quote_ctx() -> ft.OpenQuoteContext:
    return ft.OpenQuoteContext(host=FUTU_HOST, port=FUTU_PORT)


def get_trade_ctx() -> ft.OpenUSTradeContext:
    return ft.OpenUSTradeContext(host=FUTU_HOST, port=FUTU_PORT)


def us_symbol(ticker: str) -> str:
    """Convert plain ticker to Futu US market symbol."""
    ticker = ticker.upper().strip()
    if ticker.startswith("US."):
        return ticker
    return f"US.{ticker}"
