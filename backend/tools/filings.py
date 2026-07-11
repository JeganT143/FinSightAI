"""Agent tool: semantic search over the researched company's SEC filings.

Opens its own DB session per call — specialist agents run concurrently and
AsyncSession is not safe to share across tasks.
"""

from agents import function_tool

from backend.db.session import AsyncSessionLocal
from backend.rag.retrieval import search_chunks


@function_tool
async def search_filings(ticker: str, query: str) -> dict:
    """Search the company's latest SEC filing (10-K/10-Q) for passages relevant to a question.
    Use this to ground claims in management's own disclosures (risk factors, MD&A, legal).

    Args:
        ticker: Stock ticker symbol in uppercase, e.g. 'NVDA'
        query: A focused question, e.g. 'supply chain concentration risks' or 'revenue drivers'
    """
    async with AsyncSessionLocal() as db:
        results = await search_chunks(db, ticker, query)

    if not results:
        return {
            "ticker": ticker,
            "results": [],
            "note": "No filing passages available for this ticker — filings may not be ingested. "
            "State that filing data was unavailable; do NOT invent filing content.",
        }

    return {
        "ticker": ticker,
        "results": [
            {
                "source": r.source,
                "similarity": r.similarity,
                "passage": r.content[:1500],
            }
            for r in results
        ],
        "note": "Cite passages you use via the `citations` field (source + short quote).",
    }
