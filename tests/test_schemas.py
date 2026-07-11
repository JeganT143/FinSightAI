import pytest
from pydantic import ValidationError

from backend.schemas.agents import (
    PILLAR_WEIGHTS,
    FundamentalsOutput,
    compute_overall_score,
    verdict_band,
)
from backend.schemas.research import ResearchRequest
from evals.grounding import check_grounding, extract_numbers


def _specialist(score: float) -> FundamentalsOutput:
    return FundamentalsOutput(
        score=score,
        confidence="high",
        summary="s",
        bullets=["b1", "b2", "b3"],
        data_warnings=[],
        citations=[],
    )


class TestTickerValidation:
    def test_normalizes_case_and_whitespace(self):
        assert ResearchRequest(ticker=" nvda ").ticker == "NVDA"

    @pytest.mark.parametrize("bad", ["NVDA1", "TOOLONG", "", "N V", "$SPY"])
    def test_rejects_invalid(self, bad):
        with pytest.raises(ValidationError):
            ResearchRequest(ticker=bad)


class TestScoring:
    def test_weights_sum_to_one(self):
        assert abs(sum(PILLAR_WEIGHTS.values()) - 1.0) < 1e-9

    def test_weighted_average(self):
        score = compute_overall_score(
            fundamentals=_specialist(10),
            risk=_specialist(0),
            sentiment=_specialist(10),
            technicals=_specialist(10),
        )
        assert score == 7.0  # 10*.35 + 0*.30 + 10*.20 + 10*.15

    def test_uniform_scores_pass_through(self):
        assert compute_overall_score(*[_specialist(6)] * 4) == 6.0

    def test_score_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            _specialist(11)


class TestVerdictBands:
    @pytest.mark.parametrize(
        "score,allowed",
        [(9.0, "STRONG_BUY"), (7.0, "BUY"), (5.0, "HOLD"), (3.5, "SELL"), (1.0, "STRONG_SELL")],
    )
    def test_center_of_band(self, score, allowed):
        assert allowed in verdict_band(score)

    def test_bands_never_allow_opposite_extremes(self):
        for score in [x / 10 for x in range(0, 101)]:
            band = verdict_band(score)
            assert not ("STRONG_BUY" in band and "STRONG_SELL" in band)


class TestGrounding:
    SOURCE = {"pe_ratio": 31.07, "revenue_growth": 0.852, "price": 210.96}

    def test_extract_numbers_handles_commas(self):
        assert extract_numbers("revenue of $5,109,662 million") == [5109662.0]

    def test_grounded_report_passes(self):
        result = check_grounding("P/E of 31.07 with 85.2% revenue growth", self.SOURCE)
        assert result.violations == []
        assert result.checked == 2

    def test_percent_conversion_is_grounded(self):
        # 0.852 in source, report says 85.2%
        result = check_grounding("growth of 85.2%", self.SOURCE)
        assert result.violations == []

    def test_fabricated_number_is_caught(self):
        result = check_grounding("P/E of 31.07 and EPS of 99.42", self.SOURCE)
        assert result.violations == [99.42]

    def test_small_integers_and_years_skipped(self):
        result = check_grounding("3 bullets in 2026, score 8", self.SOURCE)
        assert result.checked == 0
