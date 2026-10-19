"""The breaking-change fixture is the product contract with exactly one column renamed, so
the CI check that it is reported as breaking keeps testing the real contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "models" / "contracts" / "product-database.odcs.yaml"
FIXTURE = ROOT / "tests" / "fixtures" / "product-database-renamed-column.odcs.yaml"


def test_fixture_differs_only_by_the_rename_and_version() -> None:
    original = CONTRACT.read_text().splitlines()
    renamed = FIXTURE.read_text().splitlines()
    assert len(original) == len(renamed)
    changed = [(a, b) for a, b in zip(original, renamed, strict=True) if a != b]
    assert changed == [
        ("version: 1.0.0", "version: 2.0.0"),
        ("      - name: email", "      - name: email_address"),
    ]
