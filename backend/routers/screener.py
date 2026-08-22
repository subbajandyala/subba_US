"""
US Stock Screeners — EMA Crossover, MA Retracement, Volume Surge, Fundamentals.
Uses yfinance for historical price data.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

router = APIRouter()
logger = logging.getLogger(__name__)

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD",
    "INTC", "QCOM", "AVGO", "CRM", "ORCL", "ADBE", "NFLX",
    "JPM", "BAC", "GS", "MS", "C", "WFC", "V", "MA", "AXP",
    "JNJ", "UNH", "PFE", "MRK", "ABBV", "LLY", "AMGN",
    "WMT", "COST", "HD", "NKE", "MCD", "SBUX", "DIS",
    "XOM", "CVX", "COP",
    "SPY", "QQQ", "IWM", "XLF", "XLK",
]


def _require_yf():
    if yf is None:
        raise HTTPException(status_code=501, detail="yfinance not installed — add it to requirements.txt")


def _download(tickers: list[str], period: str = "3mo") -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = yf.download(t, period=period, interval="1d", progress=False, auto_adjust=True)
            if not df.empty:
                result[t] = df
        except Exception as e:
            logger.debug("yf download %s: %s", t, e)
    return result


@router.get("/ema-crossover")
def ema_crossover(
    direction: str = Query("bullish", description="bullish | bearish | both"),
    fast: int = Query(20),
    slow: int = Query(50),
    lookback: int = Query(5, description="Days to look back for the cross"),
):
    _require_yf()
    hist = _download(UNIVERSE)
    results = []

    for ticker, df in hist.items():
        if len(df) < slow + lookback:
            continue

        close = df["Close"].squeeze()
        ef = close.ewm(span=fast, adjust=False).mean()
        es = close.ewm(span=slow, adjust=False).mean()

        window_f = ef.iloc[-(lookback + 1):]
        window_s = es.iloc[-(lookback + 1):]

        bull = any(
            window_f.iloc[i] < window_s.iloc[i] and window_f.iloc[i + 1] > window_s.iloc[i + 1]
            for i in range(len(window_f) - 1)
        )
        bear = any(
            window_f.iloc[i] > window_s.iloc[i] and window_f.iloc[i + 1] < window_s.iloc[i + 1]
            for i in range(len(window_f) - 1)
        )

        if direction == "bullish" and not bull:
            continue
        if direction == "bearish" and not bear:
            continue
        if direction == "both" and not (bull or bear):
            continue

        chg = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100)
        vol = int(df["Volume"].squeeze().iloc[-1]) if "Volume" in df.columns else 0

        results.append({
            "ticker": ticker,
            "close": round(float(close.iloc[-1]), 2),
            "ema_fast": round(float(ef.iloc[-1]), 2),
            "ema_slow": round(float(es.iloc[-1]), 2),
            "cross": "BULLISH" if bull else "BEARISH",
            "chg_pct": round(chg, 2),
            "volume": vol,
        })

    results.sort(key=lambda x: abs(x["ema_fast"] - x["ema_slow"]), reverse=True)
    return {"screener": "ema_crossover", "direction": direction, "fast": fast, "slow": slow, "results": results}


@router.get("/ma-retracement")
def ma_retracement(
    ma: int = Query(20, description="SMA period"),
    tolerance_pct: float = Query(1.5, description="Max % above SMA to qualify"),
):
    _require_yf()
    hist = _download(UNIVERSE)
    results = []

    for ticker, df in hist.items():
        if len(df) < ma + 3:
            continue

        close = df["Close"].squeeze()
        sma = close.rolling(ma).mean()
        last = float(close.iloc[-1])
        last_sma = float(sma.iloc[-1])

        if pd.isna(last_sma) or last_sma == 0:
            continue

        dist = (last - last_sma) / last_sma * 100
        if not (0 <= dist <= tolerance_pct):
            continue

        vol_series = df["Volume"].squeeze() if "Volume" in df.columns else None
        vol_ratio = 0.0
        if vol_series is not None:
            avg_v = float(vol_series.iloc[-21:-1].mean())
            today_v = float(vol_series.iloc[-1])
            vol_ratio = round(today_v / avg_v, 2) if avg_v > 0 else 0.0

        chg = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100)
        results.append({
            "ticker": ticker,
            "close": round(last, 2),
            "sma": round(last_sma, 2),
            "dist_pct": round(dist, 2),
            "chg_pct": round(chg, 2),
            "vol_ratio": vol_ratio,
        })

    results.sort(key=lambda x: x["dist_pct"])
    return {"screener": f"ma{ma}_retracement", "ma": ma, "results": results}


@router.get("/volume-surge")
def volume_surge(
    vol_ratio_min: float = Query(2.0),
    price_chg_min: float = Query(1.0, description="Absolute % change threshold"),
):
    _require_yf()
    hist = _download(UNIVERSE)
    results = []

    for ticker, df in hist.items():
        if len(df) < 25 or "Volume" not in df.columns:
            continue

        close = df["Close"].squeeze()
        vol = df["Volume"].squeeze()
        avg_v = float(vol.iloc[-21:-1].mean())
        today_v = float(vol.iloc[-1])

        if avg_v == 0:
            continue

        ratio = today_v / avg_v
        if ratio < vol_ratio_min:
            continue

        chg = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100)
        if abs(chg) < price_chg_min:
            continue

        results.append({
            "ticker": ticker,
            "close": round(float(close.iloc[-1]), 2),
            "chg_pct": round(chg, 2),
            "vol_ratio": round(ratio, 1),
            "today_vol": int(today_v),
            "avg_vol_20d": int(avg_v),
            "direction": "BULL" if chg > 0 else "BEAR",
        })

    results.sort(key=lambda x: x["vol_ratio"], reverse=True)
    return {"screener": "volume_surge", "results": results}


@router.get("/fundamentals")
def fundamentals(
    pe_max: float = Query(30.0),
    mktcap_min_b: float = Query(10.0, description="Min market cap in billions"),
):
    _require_yf()
    results = []

    for ticker in UNIVERSE:
        try:
            info = yf.Ticker(ticker).info
            pe = info.get("trailingPE") or info.get("forwardPE") or 0
            cap = (info.get("marketCap") or 0) / 1e9
            if pe <= 0 or pe > pe_max or cap < mktcap_min_b:
                continue
            results.append({
                "ticker": ticker,
                "name": info.get("shortName", ticker),
                "close": round(info.get("currentPrice") or 0, 2),
                "pe": round(pe, 1),
                "mktcap_b": round(cap, 1),
                "div_yield_pct": round((info.get("dividendYield") or 0) * 100, 2),
                "sector": info.get("sector", ""),
                "52w_high": round(info.get("fiftyTwoWeekHigh") or 0, 2),
                "52w_low": round(info.get("fiftyTwoWeekLow") or 0, 2),
            })
        except Exception as e:
            logger.debug("info %s: %s", ticker, e)

    results.sort(key=lambda x: x["pe"])
    return {"screener": "fundamentals", "results": results}
