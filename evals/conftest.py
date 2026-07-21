import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_addoption(parser: pytest.Parser) -> None:
    # The agent-eval-gate workflow (SAAS §10) raises this; local runs keep 0
    # so day-to-day eval runs report scores without hard-failing on them.
    parser.addoption(
        "--judge-floor",
        type=float,
        default=0.0,
        help="Fail LLM-judge evals whose scores fall below this floor (CI gate).",
    )


@pytest.fixture(scope="session")
def judge_floor(request: pytest.FixtureRequest) -> float:
    return request.config.getoption("--judge-floor")


@pytest.fixture(scope="session")
def nvda_specialists() -> dict:
    return json.loads((FIXTURES / "nvda_specialists.json").read_text())


@pytest.fixture(scope="session")
def nvda_report() -> dict:
    return json.loads((FIXTURES / "nvda_report.json").read_text())
