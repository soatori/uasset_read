"""Unit tests for tools/gen_quality_baseline.py helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Import build_sample_entry via importlib (tools/ has no __init__.py).
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "gen_quality_baseline", _ROOT / "tools" / "gen_quality_baseline.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["gen_quality_baseline"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
build_sample_entry = _mod.build_sample_entry


def test_build_sample_entry_marks_opt_in():
    doc = SimpleNamespace(diagnostics=[])
    entry = build_sample_entry(doc, "ALS_AnimBP.uasset", opt_in=True)
    assert entry["opt_in"] is True
    entry2 = build_sample_entry(doc, "BP_CombatCharacter.uasset", opt_in=False)
    assert "opt_in" not in entry2


def test_build_sample_entry_no_opt_in_by_default():
    doc = SimpleNamespace(diagnostics=[])
    entry = build_sample_entry(doc, "SomeOther.uasset")
    assert "opt_in" not in entry
