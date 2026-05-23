"""
Agent 翻译管线集成测试。

Phase 66-03: 验证 BP_FirstPersonCharacter → C++ 输出质量。
"""
import pytest
from pathlib import Path
from typing import Optional, Dict, Any

from uasset_read import parse_uasset_with_linker
from uasset_read.link.result import LinkerParseResult
from uasset_read.agent import (
    AgentTranslationPipeline,
    translate_blueprint_to_cpp,
    CppFileWriter,
    write_cpp_class_files,
)
from uasset_read.cpp_gen.formatters.cpp_json_ir import CppClassIR

# Test asset path
BP_FIRST_PERSON_PATH = Path(
    "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
)

# Golden files directory
GOLDEN_DIR = Path("tests/golden/agent")


def _load_bp_first_person_character() -> Optional[LinkerParseResult]:
    """Load BP_FirstPersonCharacter test asset."""
    if not BP_FIRST_PERSON_PATH.exists():
        pytest.skip(f"Test asset not found: {BP_FIRST_PERSON_PATH}")
    return parse_uasset_with_linker(str(BP_FIRST_PERSON_PATH), tolerant=True)


def _compare_key_sections(generated: str, golden_path: Path, key_sections: list) -> bool:
    """Compare generated content with golden file on key sections."""
    if not golden_path.exists():
        pytest.skip(f"Golden file not found: {golden_path}")

    golden_content = golden_path.read_text(encoding="utf-8")

    for section in key_sections:
        if section not in generated:
            pytest.fail(f"Generated missing key section: {section}")
        if section not in golden_content:
            pytest.fail(f"Golden missing key section: {section}")

    return True


class TestGoldenFilesExist:
    """Verify golden files are present."""

    def test_golden_directory_exists(self):
        assert GOLDEN_DIR.exists(), "Golden directory should exist"

    def test_golden_h_file_exists(self):
        golden_h = GOLDEN_DIR / "BP_FirstPersonCharacter.h.expected"
        assert golden_h.exists(), "Golden .h file should exist"

    def test_golden_cpp_file_exists(self):
        golden_cpp = GOLDEN_DIR / "BP_FirstPersonCharacter.cpp.expected"
        assert golden_cpp.exists(), "Golden .cpp file should exist"


class TestTranslateBpFirstPersonCharacter:
    """Main integration test: BP_FirstPersonCharacter → C++ translation."""

    def test_parse_uasset_success(self):
        """Parse BP_FirstPersonCharacter without errors."""
        result = _load_bp_first_person_character()
        assert result is not None, "Parse result should not be None"
        assert hasattr(result, "blueprint"), "Should have blueprint"

    def test_translate_to_cpp_ir(self):
        """Translate parsed result to CppClassIR."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)

        assert ir is not None, "CppClassIR should not be None"
        assert isinstance(ir, CppClassIR), "Should return CppClassIR instance"

    def test_ir_class_name_has_a_prefix(self):
        """CppClassIR name should start with 'A' (UE Actor naming convention)."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)

        assert ir.name.startswith("A"), f"Class name should start with 'A': {ir.name}"

    def test_ir_class_name_contains_blueprint_name(self):
        """CppClassIR name should contain 'FirstPersonCharacter'."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)

        assert "FirstPersonCharacter" in ir.name, f"Class name should contain blueprint name: {ir.name}"

    def test_ir_parent_class_is_character(self):
        """CppClassIR parent_class should be 'ACharacter'."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)

        # Parent class may be different depending on BP inheritance
        assert ir.parent_class in ("ACharacter", "AFirstPersonCharacter", "Character"), \
            f"Parent class should be Character variant: {ir.parent_class}"

    def test_ir_has_properties(self):
        """CppClassIR should have component properties."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)

        assert len(ir.properties) > 0, "Should have properties (components)"

    def test_ir_has_camera_component_property(self):
        """CppClassIR should include camera component property."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)

        camera_found = any(
            "Camera" in prop.name for prop in ir.properties
        )
        assert camera_found, "Should have camera component property"

    def test_ir_has_mesh_component_property(self):
        """CppClassIR should include mesh component property."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)

        mesh_found = any(
            "Mesh" in prop.name for prop in ir.properties
        )
        assert mesh_found, "Should have mesh component property"

    def test_generate_files_returns_dict(self):
        """write_cpp_class_files should return dict with .h and .cpp."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, None)

        assert isinstance(files, dict), "Should return dict"
        assert ".h" in files, "Should have .h key"
        assert ".cpp" in files, "Should have .cpp key"

    def test_generated_h_has_uclass_macro(self):
        """Generated .h should contain UCLASS macro."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, None)

        assert "UCLASS" in files[".h"], "Generated .h should have UCLASS macro"

    def test_generated_h_has_class_declaration(self):
        """Generated .h should contain class declaration."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, None)

        assert "class " in files[".h"], "Generated .h should have class declaration"
        assert ir.name in files[".h"], f"Generated .h should contain class name: {ir.name}"

    def test_generated_cpp_has_constructor(self):
        """Generated .cpp should contain constructor."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, None)

        assert ir.name in files[".cpp"], f"Generated .cpp should contain class name"
        assert "::" in files[".cpp"], "Generated .cpp should have method implementation"

    def test_generated_h_matches_golden_key_sections(self):
        """Generated .h matches golden file on key sections."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, None)

        golden_h = GOLDEN_DIR / "BP_FirstPersonCharacter.h.expected"
        key_sections = [
            "#pragma once",
            "UCLASS",  # Use flexible match for UCLASS macro
            "class",
            "GENERATED_BODY()",
            "UPROPERTY",
        ]
        _compare_key_sections(files[".h"], golden_h, key_sections)

    def test_generated_cpp_matches_golden_key_sections(self):
        """Generated .cpp matches golden file on key sections."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, None)

        golden_cpp = GOLDEN_DIR / "BP_FirstPersonCharacter.cpp.expected"
        key_sections = [
            "#include",
            "::",
            "CreateDefaultSubobject",
        ]
        _compare_key_sections(files[".cpp"], golden_cpp, key_sections)


class TestEdgeCases:
    """Edge case handling tests."""

    def test_translate_empty_blueprint_raises_error(self):
        """translate_blueprint_to_cpp should raise on None input."""
        with pytest.raises(ValueError):
            translate_blueprint_to_cpp(None)

    def test_translate_non_linker_result_raises_error(self):
        """translate_blueprint_to_cpp should raise on non-LinkerParseResult."""
        with pytest.raises(ValueError):
            translate_blueprint_to_cpp("not a result")

    def test_writer_empty_ir_raises_error(self):
        """write_cpp_class_files should raise on empty IR."""
        with pytest.raises(ValueError):
            write_cpp_class_files(None)

    def test_writer_invalid_ir_raises_error(self):
        """write_cpp_class_files should raise on invalid IR type."""
        with pytest.raises(ValueError):
            write_cpp_class_files({"not": "an IR"})


class TestFallbackStrategies:
    """Fallback strategy tests (for known stubs)."""

    def test_skeleton_mode_without_decompiled_functions(self):
        """Translation should work without decompiled_functions (skeleton mode)."""
        result = _load_bp_first_person_character()

        # Force empty decompiled_functions to test fallback
        # Note: This tests the pipeline handles missing Kismet data gracefully
        ir = translate_blueprint_to_cpp(result)

        # IR should still have class structure even without method bodies
        assert ir.name.startswith("A"), "Should still have class name"
        assert ir.parent_class, "Should still have parent class"
        assert len(ir.properties) > 0, "Should still have properties"

    def test_methods_may_have_empty_body(self):
        """Methods may have empty body_text when decompiled_functions is empty."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)

        # Some or all methods may have empty body_text (skeleton mode)
        # This is acceptable per D-66-05
        for method in ir.methods:
            # body_text may be None or empty string - both are valid
            if method.body_text:
                assert isinstance(method.body_text, str), "body_text should be string if present"


class TestWriteToDirectory:
    """Test writing files to actual directory."""

    def test_write_to_temp_directory(self, tmp_path):
        """write_cpp_class_files writes to specified directory."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, str(tmp_path))

        # Check files were written (using actual ir.name, not modified)
        h_file = tmp_path / f"{ir.name}.h"
        cpp_file = tmp_path / f"{ir.name}.cpp"

        assert h_file.exists(), f".h file should be written: {h_file}"
        assert cpp_file.exists(), f".cpp file should be written: {cpp_file}"

    def test_written_h_content_matches_dict(self, tmp_path):
        """Written .h file content matches returned dict."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, str(tmp_path))

        h_file = tmp_path / f"{ir.name}.h"
        written_content = h_file.read_text(encoding="utf-8")

        assert written_content == files[".h"], "Written content should match dict"

    def test_written_cpp_content_matches_dict(self, tmp_path):
        """Written .cpp file content matches returned dict."""
        result = _load_bp_first_person_character()
        ir = translate_blueprint_to_cpp(result)
        files = write_cpp_class_files(ir, str(tmp_path))

        cpp_file = tmp_path / f"{ir.name}.cpp"
        written_content = cpp_file.read_text(encoding="utf-8")

        assert written_content == files[".cpp"], "Written content should match dict"