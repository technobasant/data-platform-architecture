"""Every generated section is current, and the cost results match the model."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)


def test_generated_sections_are_current() -> None:
    r = run("scripts/build.py", "--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_cost_results_are_current() -> None:
    r = run("cost/model.py", "--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_relative_links_resolve() -> None:
    r = run("scripts/check_links.py", "--offline")
    assert r.returncode == 0, r.stdout + r.stderr
