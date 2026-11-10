"""Behavior tests for the public API of pg_plan_explainer."""

from __future__ import annotations

import pytest

import pg_plan_explainer


def test_normalize_trims_and_lowercases() -> None:
    assert pg_plan_explainer.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        pg_plan_explainer.normalize(value)


def test_version_is_semver() -> None:
    parts = pg_plan_explainer.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
