import yfinance as yf
from agents import function_tool


@function_tool
def get_fundamentals(ticker: str) -> dict:
    """
    Fetches fundamental financial metrics for a stock.
    Args:
        ticker: Stock ticker symbol in uppercase e.g. 'NVDA'
    """
    info = yf.Ticker(ticker).info
    return {
        "ticker": ticker,
        "current_price": info.get("currentPrice"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margins": info.get("profitMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        "earnings_growth": info.get("earningsGrowth"),
    }
