"""Contract checks: the breaking-change fixture stays a one-column diff from the real
product contract, every contract property carries a classification (0011), and no property
of the published output contract is classified personal (0017)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "models" / "contracts" / "product-database.odcs.yaml"
FIXTURE = ROOT / "tests" / "fixtures" / "product-database-renamed-column.odcs.yaml"
CONTRACTS_DIR = ROOT / "models" / "contracts"
USAGE_MART = CONTRACTS_DIR / "usage-mart.odcs.yaml"
VALID_CLASSES = {"public", "internal", "confidential", "personal"}


def test_fixture_differs_only_by_the_rename_and_version() -> None:
    original = CONTRACT.read_text().splitlines()
    renamed = FIXTURE.read_text().splitlines()
    assert len(original) == len(renamed)
    changed = [(a, b) for a, b in zip(original, renamed, strict=True) if a != b]
    assert changed == [
        ("version: 1.0.0", "version: 2.0.0"),
        ("      - name: email", "      - name: email_address"),
    ]


def _load_contracts() -> dict[str, dict]:
    return {path.name: yaml.safe_load(path.read_text()) for path in sorted(CONTRACTS_DIR.glob("*.odcs.yaml"))}


def test_every_contract_property_is_classified() -> None:
    problems = []
    for name, contract in _load_contracts().items():
        for table in contract.get("schema", []):
            for prop in table.get("properties", []):
                classification = prop.get("classification")
                if classification not in VALID_CLASSES:
                    problems.append(
                        f"{name}: {table.get('name')}.{prop.get('name')} classification {classification!r}"
                    )
    assert not problems, problems


def test_output_contract_has_no_personal_property() -> None:
    """0017: a mart column tagged personal fails the build; the usage mart is the one
    output contract today, and it must publish none."""
    contract = yaml.safe_load(USAGE_MART.read_text())
    personal = [
        f"{table['name']}.{prop['name']}"
        for table in contract.get("schema", [])
        for prop in table.get("properties", [])
        if prop.get("classification") == "personal"
    ]
    assert not personal, personal
