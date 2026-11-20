"""Tests for the `sales-automation` console command.

The command is declared in pyproject.toml as
`sales-automation = "sales_automation.cli:main"`.

- test_console_script_entry_point_declared always runs: it checks the
  installed distribution metadata when the package is installed, and
  otherwise parses pyproject.toml directly (CI installs only
  requirements.txt, so the distribution metadata is not there).
- The subprocess tests only run when the command is actually installed
  (e.g. after `pip install -e .`); otherwise they skip, so they never
  fail in plain CI runs.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from sales_automation.cli import main as cli_main

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TARGET = "sales_automation.cli:main"


def _command_path():
    """Path to the installed `sales-automation` script, or None.

    `shutil.which` only finds it when the venv bin dir is on PATH; the
    script also always sits next to the venv's own Python, so check
    there too. This is what makes the subprocess tests run in a fresh
    `pip install -e .` venv even without activating it.
    """
    found = shutil.which("sales-automation")
    if found:
        return found
    candidate = Path(sys.executable).with_name("sales-automation")
    return str(candidate) if candidate.exists() else None


COMMAND = _command_path()


def _scripts_from_pyproject() -> dict[str, str]:
    """Read [project.scripts] from pyproject.toml without extra deps."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 has no tomllib
        tomllib = None
    if tomllib is not None:
        data = tomllib.loads(text)
        return dict(data["project"]["scripts"])
    # Fallback: scan the [project.scripts] section line by line.
    scripts: dict[str, str] = {}
    in_scripts = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_scripts = stripped == "[project.scripts]"
            continue
        if in_scripts and stripped:
            m = re.match(r'([\w-]+)\s*=\s*"([^"]+)"', stripped)
            if m:
                scripts[m.group(1)] = m.group(2)
    assert scripts, "no [project.scripts] entries found in pyproject.toml"
    return scripts


def test_console_script_entry_point_declared():
    """`sales-automation` must point at sales_automation.cli:main."""
    try:
        dist = importlib.metadata.distribution("shop-sales-automation")
    except importlib.metadata.PackageNotFoundError:
        dist = None
    if dist is not None:
        scripts = {ep.name: ep.value for ep in dist.entry_points}
    else:
        scripts = _scripts_from_pyproject()
    assert scripts.get("sales-automation") == EXPECTED_TARGET

    module_name, _, attr = EXPECTED_TARGET.partition(":")
    target = getattr(importlib.import_module(module_name), attr)
    assert target is cli_main


@pytest.mark.skipif(
    COMMAND is None,
    reason="sales-automation command not installed (pip install -e .)",
)
def test_installed_command_runs_end_to_end(tmp_path):
    """The installed command cleans a CSV and writes the xlsx workbook."""
    messy = tmp_path / "in.csv"
    messy.write_text("Date,Item,Qty,Price\n2026-10-10,Sugar,10,100\n2026-10-10,Sugar,10,100\n")
    out = tmp_path / "out"
    r = subprocess.run(
        [COMMAND, str(messy), "-o", str(out), "--format", "xlsx"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert (out / "sales_clean.xlsx").exists()
    assert (out / "report.txt").exists()
    assert not (out / "sales_clean.csv").exists()
    back = pd.read_excel(out / "sales_clean.xlsx", sheet_name="Cleaned Data")
    assert len(back) == 1  # duplicate removed
    assert "[OK]" in r.stdout


@pytest.mark.skipif(
    COMMAND is None,
    reason="sales-automation command not installed (pip install -e .)",
)
def test_installed_command_help():
    """`sales-automation --help` lists the CLI options."""
    r = subprocess.run(
        [COMMAND, "--help"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0
    assert "--format" in r.stdout
    assert "sales-automation" in r.stdout  # argparse prog = script name
    assert "Clean a messy shop sales CSV" in r.stdout
