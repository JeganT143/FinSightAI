import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def nvda_specialists() -> dict:
    return json.loads((FIXTURES / "nvda_specialists.json").read_text())


@pytest.fixture(scope="session")
def nvda_report() -> dict:
    return json.loads((FIXTURES / "nvda_report.json").read_text())
