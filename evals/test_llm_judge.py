import pytest
from dotenv import load_dotenv

from evals.judges import judge_report

load_dotenv()

pytestmark = pytest.mark.llm_eval


async def test_judge_scores_report_quality(nvda_specialists, nvda_report):
    scores = await judge_report(
        specialists=nvda_specialists["specialist_outputs"],
        report=nvda_report["report"],
    )
    print(f"\nJudge ({scores.rationale[:200]}...)")
    print(
        f"groundedness={scores.groundedness} completeness={scores.completeness} "
        f"actionability={scores.actionability}"
    )
    assert scores.groundedness >= 3.5, scores.rationale
    assert scores.completeness >= 3.0, scores.rationale
    assert scores.actionability >= 3.0, scores.rationale
