"""Section-aware chunking of SEC filings (ADR-5).

Filings are split on Item boundaries FIRST so every chunk carries a citation
('10-K Item 1A — Risk Factors'), then token-windowed to embedding-friendly
sizes. Section detection is heuristic (EDGAR HTML varies wildly); when it
fails we fall back to chunking the whole document as one 'FULL' section —
degraded citations beat no grounding.
"""

import re
from dataclasses import dataclass

import tiktoken

from backend.core.config import settings

# High-signal 10-K/10-Q items worth embedding. Everything else (exhibits,
# signatures, mine-safety disclosures) is noise at retrieval time.
SECTION_TITLES: dict[str, str] = {
    "1": "Business",
    "1A": "Risk Factors",
    "2": "Properties / MD&A (10-Q)",
    "3": "Legal Proceedings",
    "5": "Market for Common Equity",
    "7": "Management's Discussion and Analysis",
    "7A": "Market Risk Disclosures",
    "8": "Financial Statements",
}

_ITEM_RE = re.compile(r"\bitem\s+(\d{1,2}[abc]?)[\s.:—-]", re.IGNORECASE)

_encoding = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    item: str
    section_title: str
    chunk_index: int
    content: str


def split_sections(text: str) -> list[tuple[str, str, str]]:
    """Return [(item, title, section_text)] for high-signal items.

    Heuristic: an item number can appear many times (table of contents,
    cross-references, body). The body occurrence is almost always the LAST one
    followed by substantial content, so we keep the last match per item and
    slice between consecutive kept positions.
    """
    matches = [(m.group(1).upper(), m.start()) for m in _ITEM_RE.finditer(text)]
    if not matches:
        return [("FULL", "Full Filing", text)]

    last_pos: dict[str, int] = {}
    for item, pos in matches:
        last_pos[item] = pos

    boundaries = sorted(last_pos.items(), key=lambda kv: kv[1])
    sections: list[tuple[str, str, str]] = []
    for i, (item, start) in enumerate(boundaries):
        if item not in SECTION_TITLES:
            continue
        end = boundaries[i + 1][1] if i + 1 < len(boundaries) else len(text)
        body = text[start:end].strip()
        if len(body) >= 500:  # skip TOC stubs and empty incorporation-by-reference items
            sections.append((item, SECTION_TITLES[item], body))

    return sections or [("FULL", "Full Filing", text)]


def chunk_section(
    item: str,
    title: str,
    text: str,
    chunk_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[Chunk]:
    """Sliding token window within one section."""
    size = chunk_tokens or settings.chunk_size_tokens
    overlap = overlap_tokens or settings.chunk_overlap_tokens
    tokens = _encoding.encode(text, disallowed_special=())

    chunks: list[Chunk] = []
    step = size - overlap
    for i, start in enumerate(range(0, len(tokens), step)):
        window = tokens[start : start + size]
        if len(window) < 50 and i > 0:  # ignore a tiny tail window
            break
        chunks.append(
            Chunk(item=item, section_title=title, chunk_index=i, content=_encoding.decode(window))
        )
    return chunks


def chunk_filing(text: str, max_chunks: int = 400) -> list[Chunk]:
    """Full pipeline: section split -> token windows, bounded for cost safety."""
    chunks: list[Chunk] = []
    for item, title, body in split_sections(text):
        chunks.extend(chunk_section(item, title, body))
        if len(chunks) >= max_chunks:
            break
    return chunks[:max_chunks]


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text, disallowed_special=()))
