"""Deterministic grounding checker (ADR-9).

Answers mechanically: does every number the report asserts exist in the
specialist data? This is the zero-cost tier of the eval harness — it catches
fabricated figures without an LLM call, and the same logic backs the
`llm_eval` judge's groundedness rubric.

Heuristics, on purpose:
- Small integers (<= 12) and year-like numbers are skipped — they're almost
  always list indices, rubric scores, or dates, and flagging them would drown
  real violations in noise.
- A report number is grounded if it appears in the source data literally,
  numerically (0.5% relative tolerance for rounding), or as a percent
  re-expression (x100 / /100) — specialists legitimately convert 0.852 -> 85.2%.
"""

import json
import re
from dataclasses import dataclass

_NUM_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


def extract_numbers(text: str) -> list[float]:
    values = []
    for raw in _NUM_RE.findall(text):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


def _is_skippable(value: float) -> bool:
    if abs(value) <= 12 and value == int(value):
        return True  # indices, scores, "3 bullet points", RSI-14 style params
    if 1900 <= value <= 2100 and value == int(value):
        return True  # years
    return False


def _matches(report_value: float, source_values: list[float], rel_tol: float = 0.005) -> bool:
    candidates = (report_value, report_value / 100, report_value * 100)
    for candidate in candidates:
        for source in source_values:
            if source == 0:
                if candidate == 0:
                    return True
                continue
            if abs(candidate - source) / abs(source) <= rel_tol:
                return True
    return False


@dataclass
class GroundingResult:
    checked: int
    violations: list[float]

    @property
    def grounded_ratio(self) -> float:
        return 1.0 if self.checked == 0 else 1 - len(self.violations) / self.checked


def check_grounding(report_text: str, source_data: dict) -> GroundingResult:
    """Every non-trivial number in `report_text` must exist in `source_data`."""
    source_json = json.dumps(source_data)
    source_values = extract_numbers(source_json)

    violations = []
    checked = 0
    for value in extract_numbers(report_text):
        if _is_skippable(value):
            continue
        checked += 1
        if not _matches(value, source_values):
            violations.append(value)
    return GroundingResult(checked=checked, violations=violations)
