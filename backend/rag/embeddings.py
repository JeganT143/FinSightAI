"""Embedding client (ADR-5): text-embedding-3-small, batched, cost-tracked."""

from dataclasses import dataclass

from openai import AsyncOpenAI

from backend.core.config import estimate_cost_usd, settings

_client: AsyncOpenAI | None = None

_BATCH_SIZE = 128


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    total_tokens: int
    cost_usd: float


async def embed_texts(texts: list[str]) -> EmbeddingResult:
    client = _get_client()
    vectors: list[list[float]] = []
    total_tokens = 0

    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        resp = await client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
            dimensions=settings.embedding_dimensions,
        )
        vectors.extend(item.embedding for item in resp.data)
        total_tokens += resp.usage.total_tokens

    return EmbeddingResult(
        vectors=vectors,
        total_tokens=total_tokens,
        cost_usd=estimate_cost_usd(settings.embedding_model, total_tokens, 0),
    )


async def embed_query(text: str) -> list[float]:
    result = await embed_texts([text])
    return result.vectors[0]
