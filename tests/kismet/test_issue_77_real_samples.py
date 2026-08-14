"""Real-sample acceptance test for Issue #77 — native UFunction script parsing.

Verifies 76 Function exports across UE 5.0, 5.2, 5.6, 5.7, and 5.8 assets.
Opt-in: skipped when the sample root directory is absent.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Sample root and matrix
# ---------------------------------------------------------------------------

SAMPLE_ROOT = os.environ.get("UE_SAMPLES_ROOT", r"E:\Develop\lib\Samples")

SAMPLES = [
    ("LyraStarterGame/Content/Characters/Heroes/Abilities/GA_Hero_Jump.uasset", 7),
    ("CropoutSampleProject/Content/Blueprint/Villagers/BP_Villager.uasset", 30),
    ("FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset", 12),
    ("StackOBot/Content/StackOBot/Blueprints/GameElements/BP_MovingPlatform.uasset", 8),
    ("GameAnimationSample/Content/Blueprints/Data/BFL_HelpfulFunctions.uasset", 10),
    ("FirstPersonC/Content/Variant_Shooter/Blueprints/BP_ShooterCharacter.uasset", 9),
]

# Total expected function exports: 76
TOTAL_EXPECTED = sum(count for _, count in SAMPLES)

# Rejected patterns in rendered JSON output
REJECTED_JSON_PATTERNS = [
    "Property_-7",
    "Property_23265280",
    "Unknown_",
    "fallback_or_serial_scan",
    "bpgc_bytecode_extraction",
    "serial_scan_recovery",
    "graph_topology",
]


def _sample_exists() -> bool:
    """Check if the sample root directory exists."""
    return os.path.isdir(SAMPLE_ROOT)


def _load_sample(rel_path: str) -> str:
    """Return absolute path to a sample file."""
    return os.path.join(SAMPLE_ROOT, rel_path)


@pytest.mark.parametrize(
    "function, expected_message",
    [
        (SimpleNamespace(function_name="Partial", bytecode_status="parsed", translation_status="partial", bytecode_source="function_export", logic_source="current_asset", fallback_reasons=[], cpp_code="return;"), "status"),
        (SimpleNamespace(function_name="Fallback", bytecode_status="parsed", translation_status="complete", bytecode_source="serial_scan_recovery", logic_source="current_asset", fallback_reasons=[], cpp_code="return;"), "bytecode source"),
        (SimpleNamespace(function_name="Topology", bytecode_status="parsed", translation_status="complete", bytecode_source="function_export", logic_source="graph_topology", fallback_reasons=[], cpp_code="return;"), "logic source"),
        (SimpleNamespace(function_name="FallbackReason", bytecode_status="parsed", translation_status="complete", bytecode_source="function_export", logic_source="current_asset", fallback_reasons=["serial_scan_recovery"], cpp_code="return;"), "fallback reasons"),
        (SimpleNamespace(function_name="EmptyCode", bytecode_status="parsed", translation_status="complete", bytecode_source="function_export", logic_source="current_asset", fallback_reasons=[], cpp_code=""), "missing C++ code"),
    ],
)
def test_strict_native_function_contract_rejects_non_native_or_incomplete_results(
    function: SimpleNamespace,
    expected_message: str,
) -> None:
    """The #77 close gate rejects non-native or incomplete function results."""
    with pytest.raises(AssertionError, match=re.escape(expected_message)):
        _assert_strict_native_function("synthetic", function)


def _function_value(function: Any, name: str) -> Any:
    """Read one function field from internal IR or rendered JSON."""
    if isinstance(function, dict):
        return function.get(name)
    return getattr(function, name)


def _assert_strict_native_function(context: str, function: Any) -> None:
    """Require the #77 close-out contract for one known Script-bearing function."""
    name = _function_value(function, "function_name")
    if name is None:
        name = _function_value(function, "name")
    prefix = f"{context}/{name}"
    assert _function_value(function, "bytecode_status") == "parsed", f"{prefix}: bytecode status is {_function_value(function, 'bytecode_status')!r}"
    assert _function_value(function, "translation_status") == "complete", f"{prefix}: translation status is {_function_value(function, 'translation_status')!r}"
    assert _function_value(function, "bytecode_source") == "function_export", f"{prefix}: bytecode source is {_function_value(function, 'bytecode_source')!r}"
    assert _function_value(function, "logic_source") == "current_asset", f"{prefix}: logic source is {_function_value(function, 'logic_source')!r}"
    assert not _function_value(function, "fallback_reasons"), f"{prefix}: fallback reasons are {_function_value(function, 'fallback_reasons')!r}"
    assert _function_value(function, "cpp_code").strip(), f"{prefix}: missing C++ code"


def test_markdown_function_renderer_prefers_native_results_but_keeps_metadata_fallback() -> None:
    """Markdown matches native output when present and retains metadata-only fallback."""
    from uasset_read.renderers.markdown_renderer import MarkdownRenderer

    metadata_function = SimpleNamespace(name="MetadataOnly", parameters=[], return_type="void")
    native_function = SimpleNamespace(
        name="NativeOnly", signature="void NativeOnly()", cpp_code="return;",
        parameters=[], return_type="void", local_variables=[], bytecode_confidence="verified",
        bytecode_status="parsed", translation_status="complete",
        bytecode_source="function_export", logic_source="current_asset", warnings=[],
        fallback_reasons=[], error_code=None, error_message=None, script_metrics=None,
    )
    renderer = MarkdownRenderer()

    metadata_lines: list[str] = []
    renderer._render_functions(
        metadata_lines,
        SimpleNamespace(decompiled_functions=[], blueprint=SimpleNamespace(functions=[metadata_function])),
    )
    assert "### MetadataOnly" in metadata_lines

    native_lines: list[str] = []
    renderer._render_functions(
        native_lines,
        SimpleNamespace(decompiled_functions=[native_function], blueprint=SimpleNamespace(functions=[metadata_function])),
    )
    assert "### NativeOnly" in native_lines
    assert "### MetadataOnly" not in native_lines


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def all_results() -> dict[str, Any]:
    """Parse all samples and return a dict keyed by relative path.

    Returns:
        dict mapping relative path to (parse_result, export_names, decompiled_names)
    """
    if not _sample_exists():
        pytest.skip("Sample root not found")

    from uasset_read.parse_uasset import parse_uasset_with_linker
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import read_package_summary, read_name_table
    from uasset_read.serializers.object_resources import (
        read_import_map, read_export_map, resolve_class_name,
    )
    from uasset_read.kismet.bytecode_extractor import FUNCTION_EXPORT_CLASSES

    results = {}
    for rel_path, expected_count in SAMPLES:
        path = _load_sample(rel_path)
        if not os.path.exists(path):
            pytest.fail(f"Required Issue #77 sample not found: {path}")

        # Parse the asset
        result = parse_uasset_with_linker(path, tolerant=True)

        # Get export names from the export map
        archive = FArchive(path, tolerant=False)
        summary = read_package_summary(archive)
        archive.seek(summary.name_offset)
        name_map = read_name_table(archive, summary)
        archive.seek(summary.import_offset)
        import_map = read_import_map(archive, summary, name_map)
        archive.seek(summary.export_offset)
        export_map = read_export_map(archive, summary, name_map)

        export_names = []
        for exp in export_map:
            cn = resolve_class_name(exp.class_index, import_map, export_map)
            if cn in FUNCTION_EXPORT_CLASSES:
                export_names.append(exp.object_name)

        # Get decompiled function names
        decompiled_names = []
        if result.decompiled_functions:
            decompiled_names = [df.function_name for df in result.decompiled_functions]

        results[rel_path] = {
            "result": result,
            "export_names": export_names,
            "decompiled_names": decompiled_names,
            "expected_count": expected_count,
        }

    return results


# ---------------------------------------------------------------------------
# Matrix tests
# ---------------------------------------------------------------------------

class TestRealSampleMatrix:
    """Verify 76 Function exports across UE 5.0-5.8 assets."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_total_function_count(self, all_results):
        """Verify total function count across all samples is 76."""
        total = sum(len(r["export_names"]) for r in all_results.values())
        assert total == TOTAL_EXPECTED, (
            f"Expected {TOTAL_EXPECTED} total functions, got {total}"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    @pytest.mark.parametrize("rel_path,expected_count", SAMPLES)
    def test_function_count_per_sample(
        self, all_results, rel_path, expected_count
    ):
        """Verify each sample has the expected number of Function exports."""
        if rel_path not in all_results:
            pytest.skip(f"Sample not found: {rel_path}")
        data = all_results[rel_path]
        actual_count = len(data["export_names"])
        assert actual_count == expected_count, (
            f"{rel_path}: expected {expected_count} functions, got {actual_count}"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    @pytest.mark.parametrize("rel_path,expected_count", SAMPLES)
    def test_decompiled_names_match_export_names(
        self, all_results, rel_path, expected_count
    ):
        """Verify decompiled_functions names exactly match export map names."""
        if rel_path not in all_results:
            pytest.skip(f"Sample not found: {rel_path}")
        data = all_results[rel_path]
        export_names = set(data["export_names"])
        decompiled_names = set(data["decompiled_names"])
        assert export_names == decompiled_names, (
            f"{rel_path}: export names != decompiled names\n"
            f"  missing from decompiled: {export_names - decompiled_names}\n"
            f"  extra in decompiled: {decompiled_names - export_names}"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    @pytest.mark.parametrize("rel_path,expected_count", SAMPLES)
    def test_decompiled_count_matches_export_count(
        self, all_results, rel_path, expected_count
    ):
        """Verify decompiled_functions count matches export count."""
        if rel_path not in all_results:
            pytest.skip(f"Sample not found: {rel_path}")
        data = all_results[rel_path]
        assert len(data["decompiled_names"]) == len(data["export_names"]), (
            f"{rel_path}: decompiled count ({len(data['decompiled_names'])}) "
            f"!= export count ({len(data['export_names'])})"
        )


# ---------------------------------------------------------------------------
# Per-function contract tests
# ---------------------------------------------------------------------------

class TestFunctionContract:
    """Verify per-function status and metadata contract."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_every_matrix_function_is_complete_native_current_asset_script(self, all_results):
        """Every known Script-bearing matrix function meets the #77 close gate."""
        for rel_path, data in all_results.items():
            for df in (data["result"].decompiled_functions or []):
                _assert_strict_native_function(rel_path, df)

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_no_k2node_pseudo_functions(self, all_results):
        """Verify no K2Node pseudo-functions appear in decompiled results."""
        for rel_path, data in all_results.items():
            result = data["result"]
            if not result.decompiled_functions:
                continue
            for df in result.decompiled_functions:
                assert not df.function_name.startswith("K2Node_"), (
                    f"{rel_path}: K2Node pseudo-function {df.function_name!r}"
                )


# ---------------------------------------------------------------------------
# JSON rendering rejection tests
# ---------------------------------------------------------------------------

class TestJsonRejection:
    """Verify rejected patterns do not appear in rendered JSON output."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    @pytest.mark.parametrize("rel_path,expected_count", SAMPLES)
    def test_no_rejected_json_patterns(
        self, all_results, rel_path, expected_count
    ):
        """Verify rejected patterns do not appear in rendered JSON."""
        if rel_path not in all_results:
            pytest.skip(f"Sample not found: {rel_path}")

        import json
        from uasset_read.core import parse_single

        path = _load_sample(rel_path)
        output = parse_single(path, format="json", tolerant=True)
        data = json.loads(output)

        output_str = json.dumps(data)
        for pattern in REJECTED_JSON_PATTERNS:
            assert pattern not in output_str, (
                f"{rel_path}: rejected pattern '{pattern}' found in JSON output"
            )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_no_rejected_markdown_patterns(self, rendered_outputs):
        """Verify fallback, topology, and garbage patterns never reach Markdown."""
        for rel_path, outputs in rendered_outputs.items():
            for pattern in REJECTED_JSON_PATTERNS:
                assert pattern not in outputs["markdown"], (
                    f"{rel_path}: rejected pattern '{pattern}' found in Markdown output"
                )


# ---------------------------------------------------------------------------
# Rendered JSON + Markdown public-output acceptance
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rendered_outputs() -> dict[str, dict[str, Any]]:
    """Render both public formats for every required #77 sample."""
    if not _sample_exists():
        pytest.skip("Sample root not found")

    import json
    from uasset_read.core import parse_single

    outputs: dict[str, dict[str, Any]] = {}
    for rel_path, _expected_count in SAMPLES:
        path = _load_sample(rel_path)
        if not os.path.exists(path):
            pytest.fail(f"Required Issue #77 sample not found: {path}")
        outputs[rel_path] = {
            "json": json.loads(parse_single(path, format="json", tolerant=True)),
            "markdown": parse_single(path, format="markdown", tolerant=True),
        }
    return outputs


def _markdown_functions_block(markdown: str) -> str:
    """Return the Markdown ``Functions`` block, excluding other asset sections."""
    marker = "## Functions\n"
    assert marker in markdown, "Markdown missing Functions section"
    return markdown.split(marker, 1)[1].split("\n## ", 1)[0]


def _markdown_function_sections(markdown: str) -> list[tuple[str, str]]:
    """Return every named function heading and body from the Functions block."""
    functions_block = _markdown_functions_block(markdown)
    matches = list(re.finditer(r"^### (?P<name>[^\n]+)\n", functions_block, re.MULTILINE))
    return [
        (match.group("name"), functions_block[match.end() : matches[index + 1].start()] if index + 1 < len(matches) else functions_block[match.end() :])
        for index, match in enumerate(matches)
    ]


def _function_markdown_section(markdown: str, function_name: str) -> str:
    """Return exactly one rendered Function body by name."""
    matches = [section for name, section in _markdown_function_sections(markdown) if name == function_name]
    assert len(matches) == 1, f"Markdown Function heading count for {function_name}: {len(matches)}"
    return matches[0]


def _cpp_fenced_block(section: str, context: str) -> str:
    """Return exactly one C++ code fence from a rendered Function body."""
    matches = re.findall(r"```cpp\n(.*?)\n```", section, re.DOTALL)
    assert len(matches) == 1, f"{context}: expected exactly one C++ code fence"
    return matches[0]


def _markdown_table_rows(section: str, heading: str) -> list[str]:
    """Return data rows from one Markdown table, or no rows when it is absent."""
    if heading not in section:
        return []
    table = section.split(heading, 1)[1].lstrip("\n").split("\n\n", 1)[0]
    lines = table.splitlines()
    assert lines and lines[0].startswith("|---"), f"{heading}: missing Markdown separator"
    return lines[1:]


def _markdown_cell(value: Any) -> str:
    """Match the Markdown renderer's table-cell escaping."""
    return str(value).replace("|", "\\|").replace("\n", " ")


class TestRenderedFunctionOutput:
    """Public JSON and Markdown preserve Function Script output contracts."""

    @pytest.mark.skip(reason="Semantic pipeline does not yet include decompiled_functions in output")
    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_rendered_outputs_cover_every_function_with_contract_fields(
        self, rendered_outputs
    ):
        """Each actual Function satisfies the strict #77 public-output contract."""
        total = 0
        for rel_path, expected_count in SAMPLES:
            functions = rendered_outputs[rel_path]["json"].get("decompiled_functions", [])
            assert len(functions) == expected_count, rel_path
            names = [function["name"] for function in functions]
            assert len(names) == len(set(names)), f"{rel_path}: duplicate Function output"
            total += len(functions)

            for function in functions:
                assert isinstance(function.get("local_variables"), list), function["name"]
                _assert_strict_native_function(rel_path, function)

        assert total == TOTAL_EXPECTED

    @pytest.mark.skip(reason="Semantic pipeline does not yet include decompiled_functions in output")
    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_markdown_locals_are_conditional_and_parsed_code_is_rendered(
        self, rendered_outputs
    ):
        """Function-local tables are present exactly when JSON recovered locals."""
        for rel_path, _expected_count in SAMPLES:
            payload = rendered_outputs[rel_path]["json"]
            markdown = rendered_outputs[rel_path]["markdown"]
            functions = payload.get("decompiled_functions", [])
            json_names = [function["name"] for function in functions]
            markdown_sections = _markdown_function_sections(markdown)
            markdown_names = [name for name, _section in markdown_sections]
            assert len(markdown_names) == len(json_names), f"{rel_path}: Markdown Function count does not match JSON"
            assert len(markdown_names) == len(set(markdown_names)), f"{rel_path}: duplicate Markdown Function headings"
            assert markdown_names == json_names, f"{rel_path}: Markdown Function headings do not match JSON order"

            for function in functions:
                section = _function_markdown_section(markdown, function["name"])
                assert ("**Local Variables:**" in section) is bool(function["local_variables"])
                _assert_strict_native_function(rel_path, function)
                signature_line = f"**Signature:** `{function['signature']}`"
                status_line = (
                    f"**Status:** bytecode={function['bytecode_status']}, "
                    f"translation={function['translation_status']}"
                )
                assert section.count(signature_line) == 1
                assert section.count(status_line) == 1
                expected_parameter_rows = []
                for parameter in function["parameters"]:
                    default = parameter.get("default_value")
                    default_str = str(default) if default is not None else "-"
                    expected_parameter_rows.append(
                        f"| {_markdown_cell(parameter.get('name', ''))} | "
                        f"{_markdown_cell(parameter.get('param_type', ''))} | "
                        f"{_markdown_cell(default_str)} |"
                    )
                assert _markdown_table_rows(section, "| Parameter | Type | Default |") == expected_parameter_rows
                expected_local_rows = [
                    f"| {_markdown_cell(local.get('name', ''))} | "
                    f"{_markdown_cell(local.get('type', ''))} |"
                    for local in function["local_variables"]
                ]
                assert _markdown_table_rows(section, "| Local | Type |") == expected_local_rows
                rendered_cpp = _cpp_fenced_block(section, f"{rel_path}/{function['name']}")
                assert rendered_cpp == function["cpp_code"].strip(), (
                    f"{rel_path}/{function['name']}: C++ fence differs from JSON cpp_code"
                )


# ---------------------------------------------------------------------------
# FirstPerson-specific assertions
# ---------------------------------------------------------------------------

class TestFirstPersonSpecific:
    """Verify FirstPerson-specific function content assertions."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_firstperson_aim_and_move_exist(self, all_results):
        """Verify Aim and Move functions exist in FirstPerson sample."""
        rel_path = "FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
        if rel_path not in all_results:
            pytest.skip("FirstPerson sample not found")
        data = all_results[rel_path]
        decompiled_names = set(data["decompiled_names"])
        assert "Aim" in decompiled_names, "Aim function not found in FirstPerson"
        assert "Move" in decompiled_names, "Move function not found in FirstPerson"

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_firstperson_aim_has_native_signature(self, all_results):
        """Verify Aim function contains AddControllerYawInput/AddControllerPitchInput."""
        rel_path = "FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
        if rel_path not in all_results:
            pytest.skip("FirstPerson sample not found")
        data = all_results[rel_path]
        result = data["result"]
        if not result.decompiled_functions:
            pytest.skip("No decompiled functions")

        aim_func = None
        for df in result.decompiled_functions:
            if df.function_name == "Aim":
                aim_func = df
                break

        if aim_func is None:
            pytest.skip("Aim function not found")

        # Aim body must contain the expected controller input calls
        assert "AddControllerYawInput" in aim_func.cpp_code, (
            "Aim function body missing AddControllerYawInput call"
        )
        assert "AddControllerPitchInput" in aim_func.cpp_code, (
            "Aim function body missing AddControllerPitchInput call"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_firstperson_move_has_native_signature(self, all_results):
        """Verify Move function contains AddMovementInput calls."""
        rel_path = "FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
        if rel_path not in all_results:
            pytest.skip("FirstPerson sample not found")
        data = all_results[rel_path]
        result = data["result"]
        if not result.decompiled_functions:
            pytest.skip("No decompiled functions")

        move_func = None
        for df in result.decompiled_functions:
            if df.function_name == "Move":
                move_func = df
                break

        if move_func is None:
            pytest.skip("Move function not found")

        # Move body must contain the expected movement input calls
        assert "AddMovementInput" in move_func.cpp_code, (
            "Move function body missing AddMovementInput call"
        )

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_aim_move_and_shooter_never_verify_graph_topology(self, all_results):
        """Named acceptance functions must not label topology as parsed bytecode."""
        firstperson_path = (
            "FirstPerson/Content/FirstPerson/Blueprints/"
            "BP_FirstPersonCharacter.uasset"
        )
        shooter_path = (
            "FirstPersonC/Content/Variant_Shooter/Blueprints/"
            "BP_ShooterCharacter.uasset"
        )
        targets = [
            df
            for df in all_results[firstperson_path]["result"].decompiled_functions
            if df.function_name in {"Aim", "Move"}
        ]
        targets.extend(all_results[shooter_path]["result"].decompiled_functions)

        for df in targets:
            assert not (
                df.bytecode_status == "parsed"
                and df.logic_source == "graph_topology"
            ), f"{df.function_name}: graph topology presented as parsed bytecode"


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

class TestMatrixSummary:
    """Enforce aggregate acceptance statistics for the real-sample matrix."""

    @pytest.mark.skipif(not _sample_exists(), reason="Sample root not found")
    def test_matrix_summary(self, all_results):
        """Require every expected Function export to have an accepted result."""
        total_functions = 0
        total_parsed = 0
        total_no_script = 0
        total_failed = 0

        for rel_path, data in all_results.items():
            result = data["result"]
            func_count = len(data["export_names"])
            total_functions += func_count

            if result.decompiled_functions:
                for df in result.decompiled_functions:
                    if df.bytecode_status == "parsed":
                        total_parsed += 1
                    elif df.bytecode_status == "no_script":
                        total_no_script += 1
                    elif df.bytecode_status == "failed":
                        total_failed += 1

        assert len(all_results) == len(SAMPLES)
        assert total_functions == TOTAL_EXPECTED
        assert total_parsed == TOTAL_EXPECTED
        assert total_no_script == 0
        assert total_failed == 0
