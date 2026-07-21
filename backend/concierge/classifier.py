"""Intent classification (SAAS §8.1) — the compliance guardrail's front door.

Two layers, cheapest first:
1. Deterministic rules. The `advice_request` patterns MUST live here — the
   refusal guarantee (SAAS §9) cannot depend on a model's mood, and the
   routing evals assert these fixtures classify correctly with zero LLM
   calls.
2. A small, cheap model call for genuinely ambiguous messages only.
   If it fails (network, quota), the message degrades to `follow_up` — a
   wrong *route* answers conservatively from existing data; only the rule
   layer is allowed to be the last line for advice refusals.
"""

import logging
import re
from typing import Literal

from agents import Agent, Runner
from pydantic import BaseModel

from backend.core.config import settings

logger = logging.getLogger(__name__)

Intent = Literal["research", "follow_up", "education", "advice_request", "account"]

# --- Layer 1: rules ---------------------------------------------------------

# Personal-advice asks: first person + a buy/sell/allocation decision.
_ADVICE_PATTERNS = [
    r"\bshould\s+(i|we|you)\b.{0,40}\b(buy|sell|invest|short|hold|dump|exit)\b",
    r"\b(is|would)\s+it\s+(be\s+)?(a\s+)?good\s+(time|idea)\s+to\s+(buy|sell|invest|short)\b",
    r"\bworth\s+(buying|selling|investing|holding)\b",
    r"\b(put|move|invest)\b.{0,30}\b(my|our)\s+(savings|money|401k|pension|salary)\b",
    r"\bwhat\s+should\s+i\s+do\s+with\b",
    r"\b(all|go)\s+in\s+on\b",
    r"\bhow\s+much\s+should\s+i\s+(buy|invest|put)\b",
]

_RESEARCH_PATTERNS = [
    r"\b(research|analyze|analyse|evaluate)\s+\$?[A-Za-z]{1,5}\b",
    r"\b(run|start|do)\s+(a\s+)?(report|research|analysis)\s+(on|for)\b",
    r"\bfull\s+report\s+on\b",
]

_ACCOUNT_PATTERNS = [
    r"\b(my|our)\s+(plan|usage|quota|limit|subscription|billing|account)\b",
    r"\bhow\s+many\s+(runs|reports)\s+(do\s+i|are)\s+(have\s+)?left\b",
    r"\b(upgrade|downgrade|cancel)\b.{0,20}\b(plan|subscription)\b",
]

_EDUCATION_PATTERNS = [
    r"\bwhat\s+(is|are|does)\s+(a|an|the)?\s*(p/?e\b|peg\b|rsi\b|beta\b|10-?k\b|10-?q\b|eps\b|market\s+cap|short\s+interest|drawdown)",
    r"\bexplain\b.{0,40}\b(ratio|indicator|metric|term|filing)\b",
    r"\bhow\s+(does|do)\s+.{0,40}\b(work|calculated|computed)\b",
]


def rule_based_intent(message: str) -> Intent | None:
    """Deterministic first pass. None = ambiguous, escalate to the model."""
    text = message.lower().strip()
    for pattern in _ADVICE_PATTERNS:
        if re.search(pattern, text):
            return "advice_request"
    for pattern in _ACCOUNT_PATTERNS:
        if re.search(pattern, text):
            return "account"
    for pattern in _RESEARCH_PATTERNS:
        if re.search(pattern, text):
            return "research"
    for pattern in _EDUCATION_PATTERNS:
        if re.search(pattern, text):
            return "education"
    return None


# --- Layer 2: cheap model, ambiguous messages only --------------------------


class _IntentOutput(BaseModel):
    intent: Intent


_intent_agent = Agent(
    name="IntentClassifier",
    model=settings.intent_model,
    instructions="""
Classify the user's message into exactly one intent:
- research: asking to research/analyze a specific stock now
- follow_up: asking about reports or data they already have
- education: asking what a financial term/metric means, how something works
- advice_request: asking whether THEY should buy/sell/hold, or what to do
  with THEIR money. When in doubt between advice_request and anything else,
  choose advice_request.
- account: asking about their plan, usage, limits, or billing
""",
    output_type=_IntentOutput,
)


async def classify_intent(message: str) -> Intent:
    ruled = rule_based_intent(message)
    if ruled is not None:
        return ruled
    try:
        result = await Runner.run(_intent_agent, message)
        return result.final_output.intent
    except Exception:
        logger.exception("intent model failed; defaulting to follow_up")
        return "follow_up"
