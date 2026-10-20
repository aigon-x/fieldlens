"""Shared fixtures. Adds the project root to sys.path so tests run from any cwd."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fieldlens.synth import make_sample  # noqa: E402


@pytest.fixture(scope="session")
def clean_samples() -> list[dict]:
    # Seeds verified to contain zero defects by construction (ground truth checked in test_synth).
    return [make_sample(seed) for seed in (7000, 7001, 7010, 7014)]


@pytest.fixture(scope="session")
def scratch_sample() -> dict:
    return make_sample(7008)  # exactly one scratch


@pytest.fixture(scope="session")
def dent_sample() -> dict:
    return make_sample(7016)  # exactly one dent


@pytest.fixture(scope="session")
def stain_sample() -> dict:
    return make_sample(7020)  # exactly one stain
