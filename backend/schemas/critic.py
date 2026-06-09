from pydantic import BaseModel
from typing import Literal

class Challenge(BaseModel):
    claim: str
    reason: str
    severity: Literal["low", "high"]

class CriticOutput(BaseModel):
    challenges: list[Challenge]
    blocks_publication: bool
    overall_assessment: str
