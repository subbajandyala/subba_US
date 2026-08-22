# Subba US — Options Chain Analyzer

A full-stack US options & stock trading app powered by **MooMoo / Futu API**.

## Features

| Screen | Description |
|--------|-------------|
| **Dashboard** | Watchlist cards, account P&L summary, quick-nav |
| **Options Chain** | Full call/put chain — bid/ask, IV, Greeks (δ θ γ ν), ATM highlight, 1-click Buy/Sell modal |
| **Stock Quotes** | Live price, OHLCV, candlestick/area chart (multiple timeframes), order book |
| **Positions** | Live portfolio — cost, market value, unrealized & realized P&L |
| **Orders** | Active & historical orders with status |
| **Trade** | Place limit/market/stop orders, max-qty check, cost estimate |

## Prerequisites

1. **FutuOpenD** running locally (same gateway your MooMoo MCP uses).
   Download from: https://openapi.futunn.com/futu-api-doc/en/
   Default port: `11111`

2. Python 3.10+ and Node 18+

## Quick Start (local dev)

```bash
# 1. Clone & cd
cd subba_US

# 2. Configure backend
cp backend/.env.example backend/.env
# Edit FUTU_HOST / FUTU_PORT if FutuOpenD is not on localhost:11111
# Set TRADE_ENV=REAL and TRADE_UNLOCK_PWD=yourpwd for live trading

# 3. One command to start both
bash scripts/dev.sh
```

Open http://localhost:3000

## Docker

```bash
cp backend/.env.example backend/.env   # edit as needed
docker-compose up --build
```

## Architecture

```
Browser (Next.js :3000)
    │   API proxy  /api/* → :8000
    ▼
FastAPI (:8000)
    │   futu-api
    ▼
FutuOpenD (:11111)   ←→   MooMoo Servers
```

## Env Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `FUTU_HOST` | `127.0.0.1` | FutuOpenD host |
| `FUTU_PORT` | `11111` | FutuOpenD port |
| `TRADE_ENV` | `PAPER` | `PAPER` or `REAL` |
| `TRADE_UNLOCK_PWD` | _(empty)_ | Required for REAL trades |

> **Malaysia note:** MooMoo Malaysia accounts trade US markets. Set `TRADE_ENV=REAL` and unlock with your 6-digit trade password in `.env`.
