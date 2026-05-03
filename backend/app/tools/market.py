from typing import Optional

import httpx
import numpy as np
from agents import function_tool
from app.core.config import settings
from pydantic import BaseModel

BASE_URL = "https://api.stockdata.org/v1"


class Fundamentals(BaseModel):
    ticker: str
    pe: float | None
    pb: float | None
    revenue_ttm_usd: float | None
    eps_ttm: float | None
    market_cap_usd: float | None

    # Rick Metrics


class RiskMetrics(BaseModel):
    ticker: str
    realized_vol_30d: float
    beta_spx: Optional[float]  # Beta might not be available for all stocks
    max_drawdown_1yr: Optional[float]  # Max drawdown over the past year


@function_tool
async def get_fundamentals(ticker: str) -> Fundamentals:
    """Fetches fundamental data for a given stock ticker.

    Args:
        ticker (str): The stock ticker symbol (e.g., "AAPL" for Apple Inc.)

    Returns:
        Fundamentals: A Pydantic model containing the fundamental data.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # Get quote
        quote_res = await client.get(
            f"{BASE_URL}/quote",
            params={"symbols": ticker, "api_token": settings.stock_data_api_key},
        )
        quote_res.raise_for_status()
        quote_data = quote_res.json().get("data", [{}])[
            0
        ]  # Get the first (and only) quote result}])

        # Get Financials
        financials_res = await client.get(
            f"{BASE_URL}/financials",
            params={"symbols": ticker, "api_token": settings.stock_data_api_key},
        )
        financials_res.raise_for_status()
        financials_data = financials_res.json().get("data", [{}])[0]

        return Fundamentals(
            ticker=ticker,
            pe=quote_data.get("pe"),
            pb=quote_data.get("pb"),
            revenue_ttm_usd=financials_data.get("revenue_ttm"),
            eps_ttm=financials_data.get("eps_ttm"),
            market_cap_usd=quote_data.get("market_cap"),
        )


@function_tool
async def get_risk_metrics(ticker: str) -> RiskMetrics:
    """Fetches risk metrics for a given stock ticker.

    Args:
        ticker (str): The stock ticker symbol (e.g., "AAPL" for Apple Inc.)

    Returns:
        RiskMetrics: A Pydantic model containing the risk metrics.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # Get historical prices
        res = await client.get(
            f"{BASE_URL}/eod",
            params={
                "symbols": ticker,
                "api_token": settings.stock_data_api_key,
                "limit": 200,
            },
        )
        res.raise_for_status()
        data = res.json().get("data", [])

        if len(data) < 30:
            raise ValueError(
                f"Not enough historical data to calculate risk metrics for {ticker}"
            )

        # extract close prices
        closes = np.array([d["close"] for d in data if d.get("close") is not None])

        # Daily returns
        returns = np.diff(closes) / closes[:-1]

        # Realized volatility (30d)
        last_30d_returns = returns[-30:]
        realized_vol = float(
            np.std(last_30d_returns) * np.sqrt(252)
        )  # Annualize volatility

        # Max Drawdown (1yr)
        cumulative = np.max.accumulate(closes)
        drawdowns = (cumulative - closes) / cumulative
        max_drawdown = float(np.max(drawdowns))

        beta = None

        return RiskMetrics(
            ticker=ticker,
            realized_vol_30d=realized_vol,
            beta_spx=beta,
            max_drawdown_1yr=max_drawdown,
        )
