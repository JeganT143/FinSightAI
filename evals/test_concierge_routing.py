"""Concierge routing evals (SAAS §8/§9 exit criterion).

The advice_request fixtures MUST classify correctly at 100% through the
deterministic rule layer alone — zero model calls, zero flakiness. This is
the compliance guarantee, so these fixtures are the one place where a single
miss fails the suite.
"""

import pytest

from backend.concierge.classifier import rule_based_intent

# Every phrasing of "tell me what to do with my money" we've thought of or
# seen. Grows with every real incident (same principle as ADR-9 fixtures).
ADVICE_FIXTURES = [
    "Should I buy NVDA?",
    "should i sell my tesla shares",
    "Is it a good time to buy AAPL?",
    "Would it be a good idea to invest in AMD right now?",
    "Is NVDA worth buying at this price?",
    "Should I put my savings into TSLA?",
    "What should I do with my 401k?",
    "should we go all in on nvidia",
    "How much should I invest in MSFT?",
    "Should I hold or dump my AMZN position?",
    "Is it a good time to short GME?",
    "should you buy the dip on META",
]

RESEARCH_FIXTURES = [
    "Research NVDA",
    "analyze AMD",
    "Can you run a report on MSFT?",
    "start research for AAPL",
    "I want a full report on NFLX",
]

ACCOUNT_FIXTURES = [
    "What's my plan?",
    "How many runs do I have left?",
    "show my usage this month",
    "I want to cancel my subscription",
    "what's my quota",
]

EDUCATION_FIXTURES = [
    "What is a P/E ratio?",
    "what does RSI mean",
    "Explain the debt to equity ratio",
    "What is a 10-K filing?",
    "how does max drawdown work",
]


@pytest.mark.parametrize("message", ADVICE_FIXTURES)
def test_advice_requests_are_caught_by_rules_alone(message):
    # 100% or fail — this is the §9 compliance boundary, not a quality metric.
    assert rule_based_intent(message) == "advice_request"


@pytest.mark.parametrize("message", RESEARCH_FIXTURES)
def test_research_intents(message):
    assert rule_based_intent(message) == "research"


@pytest.mark.parametrize("message", ACCOUNT_FIXTURES)
def test_account_intents(message):
    assert rule_based_intent(message) == "account"


@pytest.mark.parametrize("message", EDUCATION_FIXTURES)
def test_education_intents(message):
    assert rule_based_intent(message) == "education"


def test_advice_beats_research_when_both_match():
    # "Should I buy X" also mentions a ticker — advice must win the tie.
    assert rule_based_intent("Should I buy NVDA after your research on it?") == "advice_request"


def test_ambiguous_messages_defer_to_model_layer():
    assert rule_based_intent("hmm, interesting, tell me more") is None
