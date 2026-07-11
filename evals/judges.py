"""Tier-2 evals (ADR-9): LLM-as-judge over golden fixtures.

Run explicitly (they cost ~ $0.02): .venv/bin/pytest evals -m llm_eval
"""

import json
import os

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "gpt-4o")


class JudgeScores(BaseModel):
    groundedness: float = Field(ge=1, le=5, description="claims supported by specialist data")
    completeness: float = Field(ge=1, le=5, description="covers all pillars, risks, and warnings")
    actionability: float = Field(ge=1, le=5, description="verdict + thesis a reader can act on")
    rationale: str


JUDGE_PROMPT = """You are grading an AI-generated equity research report against the
specialist data it was synthesized from. Score 1-5 on each dimension:

- groundedness: 5 = every claim traceable to specialist data; 1 = mostly unsupported
- completeness: 5 = all four pillars, key risks, and data warnings reflected; 1 = major omissions
- actionability: 5 = clear verdict with reasoned thesis; 1 = hedge-everything mush

Judge only against the provided data. Missing market context is NOT a flaw:
the report is supposed to use specialist data alone.

SPECIALIST DATA:
{specialists}

REPORT:
{report}
"""


async def judge_report(specialists: dict, report: dict) -> JudgeScores:
    client = AsyncOpenAI()
    response = await client.chat.completions.parse(
        model=JUDGE_MODEL,
        messages=[
            {
                "role": "user",
                "content": JUDGE_PROMPT.format(
                    specialists=json.dumps(specialists, indent=2),
                    report=json.dumps(report, indent=2),
                ),
            }
        ],
        response_format=JudgeScores,
    )
    return response.choices[0].message.parsed
