import pytest
from dotenv import load_dotenv

from evals.judges import judge_report

load_dotenv()

pytestmark = pytest.mark.llm_eval


async def test_judge_scores_report_quality(nvda_specialists, nvda_report, judge_floor):
    scores = await judge_report(
        specialists=nvda_specialists["specialist_outputs"],
        report=nvda_report["report"],
    )
    print(f"\nJudge ({scores.rationale[:200]}...)")
    print(
        f"groundedness={scores.groundedness} completeness={scores.completeness} "
        f"actionability={scores.actionability}"
    )
    # Baseline expectations always hold; --judge-floor (the §10 CI gate) can
    # only raise the bar, never lower it.
    assert scores.groundedness >= max(3.5, judge_floor), scores.rationale
    assert scores.completeness >= max(3.0, judge_floor), scores.rationale
    assert scores.actionability >= max(3.0, judge_floor), scores.rationale
