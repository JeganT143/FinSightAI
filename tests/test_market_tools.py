"""Market-tool logic tests: indicator math and payload normalization.

yfinance itself is stubbed — these verify OUR logic (RSI/SMA/drawdown
arithmetic, null-warning bookkeeping, the two news schemas yfinance has
shipped), not Yahoo's API.
"""

import types

import pandas as pd

from backend.tools import market
from backend.tools.market import _compute_technicals, _fetch_news, _null_warnings


def test_null_warnings_lists_missing_fields():
    data = {"ticker": "NVDA", "pe_ratio": 30.5, "beta": None, "peg_ratio": None}
    assert _null_warnings(data) == ["beta", "peg_ratio"]


def test_null_warnings_skips_configured_keys():
    assert _null_warnings({"ticker": None, "beta": None}) == ["beta"]


def _stub_ticker(monkeypatch, **attrs):
    """Install a fake yf.Ticker whose instances expose the given attributes."""
    monkeypatch.setattr(
        market, "yf", types.SimpleNamespace(Ticker=lambda t: types.SimpleNamespace(**attrs))
    )


def test_technicals_on_steadily_rising_series(monkeypatch):
    # 300 trading days of +0.1%/day: every indicator has a known direction.
    prices = pd.Series([100 * (1.001**i) for i in range(300)])
    hist = pd.DataFrame({"Close": prices})
    _stub_ticker(monkeypatch, history=lambda **kw: hist)

    data = _compute_technicals("TEST")

    assert data["last_close"] == round(float(prices.iloc[-1]), 2)
    assert data["return_1m_pct"] > 0
    assert data["return_1y_pct"] > 0
    assert data["sma_50"] < data["last_close"]  # rising series sits above its averages
    assert data["sma_200"] < data["sma_50"]
    assert data["rsi_14"] == 100.0  # no down days at all
    assert data["max_drawdown_1y_pct"] == 0.0
    assert data["data_warnings"] == []


def test_technicals_insufficient_history_degrades_explicitly(monkeypatch):
    hist = pd.DataFrame({"Close": pd.Series([100.0] * 10)})
    _stub_ticker(monkeypatch, history=lambda **kw: hist)

    data = _compute_technicals("TEST")
    assert data["data_warnings"] == ["insufficient price history"]
    assert "last_close" not in data  # no half-computed indicators


def test_fetch_news_handles_nested_and_flat_schemas(monkeypatch):
    items = [
        {  # yfinance >= 0.2.5x: fields nested under 'content'
            "content": {
                "title": "Nested headline",
                "provider": {"displayName": "Reuters"},
                "pubDate": "2026-07-01",
                "summary": "x" * 500,
            }
        },
        {  # older flat schema
            "title": "Flat headline",
            "publisher": "Bloomberg",
            "providerPublishTime": 1750000000,
            "summary": "short",
        },
    ]
    _stub_ticker(monkeypatch, news=items)

    headlines = _fetch_news("TEST", limit=8)
    assert headlines[0]["title"] == "Nested headline"
    assert headlines[0]["publisher"] == "Reuters"
    assert len(headlines[0]["summary"]) == 300  # truncated
    assert headlines[1]["title"] == "Flat headline"
    assert headlines[1]["publisher"] == "Bloomberg"
