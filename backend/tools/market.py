"""Market-data tools backed by yfinance.

Conventions (ADR: Failure Modes):
- Tools are async and push blocking yfinance I/O to a thread so the four
  specialist agents genuinely run in parallel.
- Missing fields come back as explicit nulls plus a `data_warnings` list.
  Agents are instructed to surface gaps, never to fill them from memory —
  the critic treats invented numbers as high-severity.
"""

import asyncio
import math
from typing import Any

import yfinance as yf
from agents import function_tool


def _null_warnings(data: dict[str, Any], skip: tuple[str, ...] = ("ticker",)) -> list[str]:
    return [k for k, v in data.items() if v is None and k not in skip]


def _fetch_info(ticker: str) -> dict[str, Any]:
    return yf.Ticker(ticker).info or {}


@function_tool
async def get_fundamentals(ticker: str) -> dict:
    """Fetch fundamental financial metrics for a stock (valuation, growth, profitability).

    Args:
        ticker: Stock ticker symbol in uppercase, e.g. 'NVDA'
    """
    info = await asyncio.to_thread(_fetch_info, ticker)
    data = {
        "ticker": ticker,
        "current_price": info.get("currentPrice"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "peg_ratio": info.get("trailingPegRatio"),
        "price_to_book": info.get("priceToBook"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "profit_margins": info.get("profitMargins"),
        "operating_margins": info.get("operatingMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        "free_cash_flow": info.get("freeCashflow"),
        "total_cash": info.get("totalCash"),
    }
    data["data_warnings"] = _null_warnings(data)
    return data


@function_tool
async def get_risk_metrics(ticker: str) -> dict:
    """Fetch risk, leverage, and volatility metrics for a stock.

    Args:
        ticker: Stock ticker symbol in uppercase, e.g. 'NVDA'
    """
    info = await asyncio.to_thread(_fetch_info, ticker)
    data = {
        "ticker": ticker,
        "beta": info.get("beta"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
        "short_ratio": info.get("shortRatio"),
        "short_percent_of_float": info.get("shortPercentOfFloat"),
        "audit_risk": info.get("auditRisk"),
        "overall_risk": info.get("overallRisk"),
    }
    data["data_warnings"] = _null_warnings(data)
    return data


@function_tool
async def get_analyst_sentiment(ticker: str) -> dict:
    """Fetch analyst recommendations, price targets, and ownership structure.

    Args:
        ticker: Stock ticker symbol in uppercase, e.g. 'NVDA'
    """
    info = await asyncio.to_thread(_fetch_info, ticker)
    data = {
        "ticker": ticker,
        "current_price": info.get("currentPrice"),
        "analyst_recommendation": info.get("recommendationKey"),
        "recommendation_mean": info.get("recommendationMean"),
        "target_mean_price": info.get("targetMeanPrice"),
        "target_high_price": info.get("targetHighPrice"),
        "target_low_price": info.get("targetLowPrice"),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "institutional_ownership": info.get("heldPercentInstitutions"),
        "insider_ownership": info.get("heldPercentInsiders"),
    }
    data["data_warnings"] = _null_warnings(data)
    return data


def _fetch_news(ticker: str, limit: int) -> list[dict]:
    items = yf.Ticker(ticker).news or []
    headlines = []
    for item in items[:limit]:
        # yfinance >= 0.2.5x nests fields under 'content'; older versions are flat.
        content = item.get("content", item)
        provider = content.get("provider") or {}
        headlines.append(
            {
                "title": content.get("title"),
                "publisher": provider.get("displayName") or content.get("publisher"),
                "published": content.get("pubDate") or content.get("providerPublishTime"),
                "summary": (content.get("summary") or "")[:300],
            }
        )
    return headlines


@function_tool
async def get_recent_news(ticker: str) -> dict:
    """Fetch recent news headlines and summaries for a stock.

    Args:
        ticker: Stock ticker symbol in uppercase, e.g. 'NVDA'
    """
    headlines = await asyncio.to_thread(_fetch_news, ticker, 8)
    return {
        "ticker": ticker,
        "headline_count": len(headlines),
        "headlines": headlines,
        "data_warnings": [] if headlines else ["no recent news found"],
    }


def _compute_technicals(ticker: str) -> dict[str, Any]:
    hist = yf.Ticker(ticker).history(period="1y", auto_adjust=True)
    if hist is None or hist.empty or len(hist) < 30:
        return {"ticker": ticker, "data_warnings": ["insufficient price history"]}

    close = hist["Close"]
    last = float(close.iloc[-1])

    def pct_return(days: int) -> float | None:
        if len(close) <= days:
            return None
        past = float(close.iloc[-days - 1])
        return round((last / past - 1) * 100, 2) if past else None

    sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    sma_200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

    # RSI(14), simple rolling-mean variant
    delta = close.diff()
    gains = delta.clip(lower=0).rolling(14).mean()
    losses = (-delta.clip(upper=0)).rolling(14).mean()
    last_gain, last_loss = float(gains.iloc[-1]), float(losses.iloc[-1])
    if last_loss == 0:
        rsi = 100.0
    else:
        rsi = 100 - 100 / (1 + last_gain / last_loss)

    daily_returns = close.pct_change().dropna()
    ann_vol = float(daily_returns.std() * math.sqrt(252) * 100)

    running_max = close.cummax()
    max_drawdown = float(((close / running_max) - 1).min() * 100)

    data = {
        "ticker": ticker,
        "last_close": round(last, 2),
        "return_1m_pct": pct_return(21),
        "return_3m_pct": pct_return(63),
        "return_6m_pct": pct_return(126),
        "return_1y_pct": pct_return(len(close) - 1),
        "sma_50": round(sma_50, 2) if sma_50 else None,
        "sma_200": round(sma_200, 2) if sma_200 else None,
        "price_vs_sma50_pct": round((last / sma_50 - 1) * 100, 2) if sma_50 else None,
        "price_vs_sma200_pct": round((last / sma_200 - 1) * 100, 2) if sma_200 else None,
        "rsi_14": round(rsi, 1),
        "annualized_volatility_pct": round(ann_vol, 1),
        "max_drawdown_1y_pct": round(max_drawdown, 1),
    }
    data["data_warnings"] = _null_warnings(data)
    return data


@function_tool
async def get_technicals(ticker: str) -> dict:
    """Compute technical indicators from 1 year of price history:
    momentum returns, moving averages, RSI, volatility, max drawdown.

    Args:
        ticker: Stock ticker symbol in uppercase, e.g. 'NVDA'
    """
    return await asyncio.to_thread(_compute_technicals, ticker)
