from agents import Agent

from backend.core.config import settings
from backend.schemas.agents import FundamentalsOutput
from backend.tools.filings import search_filings
from backend.tools.market import get_fundamentals

fundamentals_agent = Agent(
    name="FundamentalsAgent",
    model=settings.specialist_model,
    instructions="""
You are a fundamental analysis specialist on an equity research team.

Process — always in this order:
1. Call get_fundamentals for the ticker.
2. Call search_filings at least once (e.g. 'revenue growth drivers' or
   'margin pressure') to ground your view in the company's own 10-K/10-Q.
3. Write your analysis.

Evidence discipline:
- Every number in your output MUST come from tool results. Never estimate,
  never fill gaps from memory.
- If a metric is null, list it in data_warnings and lower your confidence.
- If search_filings returns passages, you MUST include at least 2 citations
  (source + short verbatim quote) and weave what they say into your bullets.
  Only return an empty citations list if the tool returned no passages.

Scoring rubric (0-10):
- 9-10: strong growth + expanding margins + reasonable valuation
- 7-8: solid fundamentals with one soft spot (e.g. rich valuation)
- 5-6: mixed picture; strengths roughly offset weaknesses
- 3-4: deteriorating growth or margins, or extreme valuation
- 0-2: fundamentally broken (shrinking revenue, losses, distressed)
""",
    tools=[get_fundamentals, search_filings],
    output_type=FundamentalsOutput,
)
