import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from routers import quotes, options, account, trading, analysis, screener, expiry, scanner

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Subba US Options Analyzer API")
    yield
    logger.info("Shutting down API")


app = FastAPI(
    title="Subba US Options Analyzer",
    description="Options chain analyzer and trading for US markets via MooMoo/Futu",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quotes.router, prefix="/api/quotes", tags=["Quotes"])
app.include_router(options.router, prefix="/api/options", tags=["Options"])
app.include_router(account.router, prefix="/api/account", tags=["Account"])
app.include_router(trading.router,   prefix="/api/trading",  tags=["Trading"])
app.include_router(analysis.router,  prefix="/api/options",  tags=["Analysis"])
app.include_router(screener.router,  prefix="/api/screener", tags=["Screener"])
app.include_router(expiry.router,    prefix="/api/expiry",   tags=["Expiry"])
app.include_router(scanner.router,   prefix="/api/scanner",  tags=["Scanner"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
