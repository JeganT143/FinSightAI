"""Tier-1 evals (ADR-9): free, deterministic, run on every CI push.

Golden fixtures are a REAL pipeline run (NVDA, recorded 2026-07-11) — the
checks assert invariants that must hold for any run, not snapshot equality.
"""

from backend.schemas.agents import (
    CriticOutput,
    FundamentalsOutput,
    ReportDraft,
    RiskOutput,
    SentimentOutput,
    TechnicalsOutput,
    compute_overall_score,
    verdict_band,
)
from evals.grounding import check_grounding

PILLAR_MODELS = {
    "fundamentals": FundamentalsOutput,
    "technicals": TechnicalsOutput,
    "risk": RiskOutput,
    "sentiment": SentimentOutput,
}


def test_specialist_outputs_validate_against_contracts(nvda_specialists):
    for pillar, model in PILLAR_MODELS.items():
        output = model.model_validate(nvda_specialists["specialist_outputs"][pillar])
        assert 0 <= output.score <= 10
        assert len(output.bullets) >= 2, f"{pillar} produced too few evidence bullets"


def test_report_validates_against_contract(nvda_report):
    ReportDraft.model_validate(nvda_report["report"])
    CriticOutput.model_validate(nvda_report["critic"])


def test_overall_score_is_correct_weighted_arithmetic(nvda_specialists, nvda_report):
    outputs = {
        pillar: model.model_validate(nvda_specialists["specialist_outputs"][pillar])
        for pillar, model in PILLAR_MODELS.items()
    }
    expected = compute_overall_score(
        fundamentals=outputs["fundamentals"],
        risk=outputs["risk"],
        sentiment=outputs["sentiment"],
        technicals=outputs["technicals"],
    )
    assert nvda_report["report"]["overall_score"] == expected


def test_verdict_consistent_with_score(nvda_report):
    report = nvda_report["report"]
    assert report["verdict"] in verdict_band(report["overall_score"])


def test_pillar_summaries_match_specialist_scores(nvda_specialists, nvda_report):
    pillar_scores = {p["pillar"]: p["score"] for p in nvda_report["report"]["pillars"]}
    assert set(pillar_scores) == set(PILLAR_MODELS), "report must cover all four pillars"
    for pillar in PILLAR_MODELS:
        assert pillar_scores[pillar] == nvda_specialists["specialist_outputs"][pillar]["score"], (
            f"synthesizer changed the {pillar} score"
        )


def test_report_numbers_are_grounded_in_specialist_data(nvda_specialists, nvda_report):
    """The signature check: no number in the report that specialists didn't produce."""
    report = nvda_report["report"]
    report_text = " ".join(
        [report["thesis"], report["narrative_markdown"], *report["key_risks"], *report["catalysts"]]
    )
    result = check_grounding(report_text, nvda_specialists["specialist_outputs"])
    assert result.checked > 0, "report contains no checkable numbers — suspiciously vague"
    assert not result.violations, (
        f"fabricated numbers in report (not in any specialist output): {result.violations}"
    )


def test_citations_carried_forward_when_specialists_cite(nvda_specialists, nvda_report):
    specialist_citations = [
        c
        for pillar in ("fundamentals", "risk")
        for c in nvda_specialists["specialist_outputs"][pillar].get("citations", [])
    ]
    if specialist_citations:
        assert nvda_report["report"]["citations"], (
            "specialists cited filings but the synthesizer dropped every citation"
        )


def test_blocking_critic_requires_high_severity(nvda_report):
    critic = CriticOutput.model_validate(nvda_report["critic"])
    if critic.blocks_publication:
        assert any(c.severity == "high" for c in critic.challenges), (
            "critic blocked publication without any high-severity challenge"
        )
