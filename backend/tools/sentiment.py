import yfinance as yf
from agents import function_tool


@function_tool
def get_market_sentiment(ticker: str) -> dict:
    """
    Fetches market sentiment indicators for a stock.
    Args:
        ticker: Stock ticker symbol in uppercase e.g. 'NVDA'
    """
    info = yf.Ticker(ticker).info
    return {
        "ticker": ticker,
        "analyst_recommendation": info.get("recommendationKey"),
        "target_price": info.get("targetMeanPrice"),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "institutional_ownership": info.get("heldPercentInstitutions"),
        "insider_ownership": info.get("heldPercentInsiders"),
    }
