import json

import redis.asyncio as aioredis
from app.core.config import settings


class SessionStore:
    TIL_SECONDS = 86_400

    def __init__(self):
        self._client: aioredis.Redis | None = None

    async def connect(self):
        self._client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    async def disconnect(self):
        if self._client:
            await self._client.aclose()

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def set(self, session_id: str, data: dict) -> None:
        await self._client.setex(
            self._key(session_id=session_id), self.TIL_SECONDS, json.dumps(data)
        )

    async def get(self, session_id: str) -> dict | None:
        raw = await self._client.get(self._key(session_id=session_id))
        return json.loads(raw) if raw else None

    async def delete(self, session_id: str) -> None:
        await self._client.delete(self._key(session_id=session_id))


session_store = SessionStore()
