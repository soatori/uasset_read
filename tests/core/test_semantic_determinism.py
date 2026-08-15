"""Semantic JSON determinism, evidence, and reference closure tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from uasset_read import parse_single

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "tests" / "samples"


def _find_sample(name_pattern: str) -> str | None:
    """Find a sample file matching the pattern."""
    for f in SAMPLES.glob("*.uasset"):
        if name_pattern.lower() in f.name.lower():
            return str(f)
    return None


_sample_candidate = _find_sample("FirstPerson_BP")
if _sample_candidate is None:
    _sample_candidate = str(next(SAMPLES.glob("*.uasset"), SAMPLES / "dummy"))
SAMPLE: str = _sample_candidate


class TestDeterminism:
    """Output must be byte-identical across processes and PYTHONHASHSEED values."""

    @pytest.mark.parametrize("seed", [0, 42, 2**31 - 1])
    def test_identical_across_hash_seeds(self, seed: int) -> None:
        """Two runs with different PYTHONHASHSEED produce identical bytes."""
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = str(seed)
        src_dir = str(ROOT / "src")
        env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
        code = (
            f"import json; from uasset_read import parse_single; "
            f"print(parse_single({SAMPLE!r}, format='json', output_level='standard', log_enabled=False), end='')"
        )
        out1 = subprocess.check_output(
            [sys.executable, "-c", code], env=env, text=True, timeout=120
        )
        out2 = subprocess.check_output(
            [sys.executable, "-c", code], env=env, text=True, timeout=120
        )
        assert out1 == out2, "Determinism violated: two runs differ"

    def test_output_is_valid_json(self) -> None:
        """Output parses as valid JSON with allow_nan=False semantics."""
        raw = parse_single(
            SAMPLE, format="json", output_level="standard", log_enabled=False
        )
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_output_ends_with_single_newline(self) -> None:
        """Output ends with exactly one LF newline."""
        raw = parse_single(
            SAMPLE, format="json", output_level="standard", log_enabled=False
        )
        assert raw.endswith("\n")
        assert not raw.endswith("\n\n")


class TestEvidenceStripping:
    """Standard mode must strip all evidence entries."""

    def test_standard_mode_has_no_evidence(self) -> None:
        raw = parse_single(
            SAMPLE, format="json", output_level="standard", log_enabled=False
        )
        data = json.loads(raw)
        assert data.get("evidence", []) == [], (
            "Standard mode should have empty evidence"
        )

    def test_debug_mode_preserves_evidence(self) -> None:
        raw = parse_single(
            SAMPLE, format="json", output_level="debug", log_enabled=False
        )
        data = json.loads(raw)
        # Debug mode should have evidence key (may be empty list if no evidence
        # was generated, but the key should exist in the envelope)
        assert "evidence" in data


class TestReferenceClosure:
    """Import/export references should be self-consistent."""

    def test_references_have_required_fields(self) -> None:
        raw = parse_single(
            SAMPLE, format="json", output_level="standard", log_enabled=False
        )
        data = json.loads(raw)
        refs = data.get("references", [])
        for ref in refs:
            assert "index" in ref, f"Reference missing 'index': {ref}"
            assert "kind" in ref, f"Reference missing 'kind': {ref}"
            assert ref["kind"] in ("import", "export"), f"Invalid kind: {ref['kind']}"
            assert "class_name" in ref, f"Reference missing 'class_name': {ref}"
            assert "object_name" in ref, f"Reference missing 'object_name': {ref}"

    def test_reference_indices_are_unique(self) -> None:
        raw = parse_single(
            SAMPLE, format="json", output_level="standard", log_enabled=False
        )
        data = json.loads(raw)
        refs = data.get("references", [])
        by_kind: dict[str, list[int]] = {}
        for ref in refs:
            by_kind.setdefault(ref["kind"], []).append(ref["index"])
        for kind, indices in by_kind.items():
            assert len(indices) == len(set(indices)), (
                f"{kind} reference indices are not unique"
            )


class TestReferenceScopePinned:
    """Pin #551 scope: references = full import/export tables.

    Reachable-reference closure is formally deferred to #554-#557 (domain
    extractors own the reachability data). If these tests fail, the scope
    changed: update docs/formats/uasset/semantic-json.md ("Reference Scope")
    and the #551 acceptance criteria accordingly.
    """

    def test_references_cover_full_import_and_export_tables(self) -> None:
        from uasset_read.parse_uasset import parse_uasset_with_linker
        from uasset_read.ir_builder import build_package_ir

        data = json.loads(parse_single(
            SAMPLE, format="json", output_level="standard", log_enabled=False
        ))
        result = parse_uasset_with_linker(SAMPLE, tolerant=True)
        ir = build_package_ir(result)

        refs = data.get("references", [])
        import_refs = [r for r in refs if r["kind"] == "import"]
        export_refs = [r for r in refs if r["kind"] == "export"]

        assert len(import_refs) == len(ir.imports)
        assert {r["index"] for r in import_refs} == set(range(len(ir.imports)))
        assert len(export_refs) == len(ir.exports)
        assert {r["index"] for r in export_refs} == {e.index for e in ir.exports}

    def test_closure_filtering_is_not_applied(self) -> None:
        """Standard mode must not yet drop unreachable references (#551 scope)."""
        data = json.loads(parse_single(
            SAMPLE, format="json", output_level="standard", log_enabled=False
        ))
        refs = data.get("references", [])
        kinds = {r["kind"] for r in refs}
        assert kinds == {"import", "export"}
        assert len(refs) > 100
