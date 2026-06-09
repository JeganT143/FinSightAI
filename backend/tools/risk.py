import yfinance as yf
from agents import function_tool

@function_tool
def get_risk_metrics(ticker: str) -> dict:
    """
    Fetches risk and volatility metrics for a stock.
    Args:
        ticker: Stock ticker symbol in uppercase e.g. 'NVDA'
    """
    info = yf.Ticker(ticker).info
    return {
        "ticker": ticker,
        "beta": info.get("beta"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
        "short_ratio": info.get("shortRatio"),
    }