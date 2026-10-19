from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def strong_ad() -> str:
    return (FIXTURES / "strong_ad.html").read_text(encoding="utf-8")


@pytest.fixture
def weak_ad() -> str:
    return (FIXTURES / "weak_ad.html").read_text(encoding="utf-8")
