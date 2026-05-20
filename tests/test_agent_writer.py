"""Tests for agent/writer.py — CppFileWriter for .h/.cpp file output.

Phase 66-02: TDD tests for C++ file generation from CppClassIR.

Tests:
1. CppFileWriter importable and callable
2. write_cpp_class_files(ir, None) returns dict with .h/.cpp text
3. write_cpp_class_files(ir, "dir") writes files to directory
4. Generated .h contains #pragma once + UCLASS macro
5. Generated .h contains correct class declaration (class X : public Y)
6. Generated .h contains UPROPERTY declarations
7. Generated .cpp contains constructor implementation
8. Generated .cpp contains method implementations (if body present)
9. Empty method.body generates declaration only (no implementation in .cpp)
"""
import os
import tempfile
from typing import Any, Dict, List

import pytest


# ============================================================================
# Test fixtures
# ============================================================================


@pytest.fixture
def sample_cpp_class_ir() -> Dict[str, Any]:
    """Create a sample CppClassIR for testing.

    Returns a dict that can be used to reconstruct a CppClassIR object.
    """
    from uasset_read.cpp_gen import (
        CppClassIR,
        CppProperty,
        CppHeaderMeta,
        CppMethodIR,
        CppCallParameter,
    )
    from uasset_read.cpp_gen.formatters import CppCallStmt

    # Create properties
    camera_prop = CppProperty(
        cpp_type="UCameraComponent*",
        name="CameraComp",
        uproperty_marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
        category="component",
        default_value=None,
        cpp_comment="First person camera",
    )

    speed_prop = CppProperty(
        cpp_type="float",
        name="MoveSpeed",
        uproperty_marks=["EditAnywhere", "BlueprintReadWrite"],
        category="Movement",
        default_value=100.0,
    )

    # Create header meta
    header_meta = CppHeaderMeta.build_from_parent("ACharacter", "ATestCharacter")

    # Create method with body
    aim_method = CppMethodIR(
        cpp_name="Aim",
        return_type="void",
        parameters=[
            CppCallParameter(name="AxisValue", cpp_type="float", direction="input")
        ],
        ufunction_specifiers=["BlueprintCallable"],
        is_override=False,
        is_const=False,
        source_node_type="K2Node_FunctionEntry",
        body=[
            CppCallStmt(target="this", method_name="AddControllerPitchInput", args=["AxisValue"])
        ],
    )

    # Create method without body (declaration only)
    empty_method = CppMethodIR(
        cpp_name="EmptyFunc",
        return_type="void",
        parameters=[],
        ufunction_specifiers=["BlueprintCallable"],
        is_override=False,
        is_const=False,
        source_node_type="K2Node_FunctionEntry",
        body=[],  # Empty body
    )

    # Create constructor IR data
    constructor_ir = {
        "component_creations": [],
        "component_assignments": [],
        "default_values": [],
    }

    # Create CppClassIR
    ir = CppClassIR(
        name="ATestCharacter",
        parent_class="ACharacter",
        header_meta=header_meta,
        properties=[camera_prop, speed_prop],
        methods=[aim_method, empty_method],
        constructor=constructor_ir,
    )

    return ir


# ============================================================================
# Tests
# ============================================================================


class TestCppFileWriterImport:
    """Test 1: CppFileWriter importable and callable."""

    def test_import_cpp_file_writer(self):
        """Test that CppFileWriter can be imported."""
        from uasset_read.agent.writer import CppFileWriter
        assert CppFileWriter is not None

    def test_import_write_cpp_class_files(self):
        """Test that write_cpp_class_files can be imported."""
        from uasset_read.agent.writer import write_cpp_class_files
        assert write_cpp_class_files is not None

    def test_cpp_file_writer_callable(self, sample_cpp_class_ir):
        """Test that CppFileWriter can be instantiated."""
        from uasset_read.agent.writer import CppFileWriter
        writer = CppFileWriter(sample_cpp_class_ir)
        assert writer is not None


class TestWriteCppClassFilesReturnsDict:
    """Test 2: write_cpp_class_files(ir, None) returns dict with .h/.cpp text."""

    def test_returns_dict_with_h_and_cpp_keys(self, sample_cpp_class_ir):
        """Test that result has .h and .cpp keys."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert ".h" in result
        assert ".cpp" in result

    def test_h_is_string(self, sample_cpp_class_ir):
        """Test that .h value is a string."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert isinstance(result[".h"], str)

    def test_cpp_is_string(self, sample_cpp_class_ir):
        """Test that .cpp value is a string."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert isinstance(result[".cpp"], str)

    def test_h_non_empty(self, sample_cpp_class_ir):
        """Test that .h content is non-empty."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert len(result[".h"]) > 0


class TestWriteCppClassFilesWritesToDirectory:
    """Test 3: write_cpp_class_files(ir, "dir") writes files to directory."""

    def test_writes_h_file(self, sample_cpp_class_ir):
        """Test that .h file is written to directory."""
        from uasset_read.agent.writer import write_cpp_class_files
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_cpp_class_files(sample_cpp_class_ir, tmpdir)
            h_path = os.path.join(tmpdir, "ATestCharacter.h")
            assert os.path.exists(h_path)

    def test_writes_cpp_file(self, sample_cpp_class_ir):
        """Test that .cpp file is written to directory."""
        from uasset_read.agent.writer import write_cpp_class_files
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_cpp_class_files(sample_cpp_class_ir, tmpdir)
            cpp_path = os.path.join(tmpdir, "ATestCharacter.cpp")
            assert os.path.exists(cpp_path)

    def test_h_file_content_matches_dict(self, sample_cpp_class_ir):
        """Test that written .h file matches dict content."""
        from uasset_read.agent.writer import write_cpp_class_files
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_cpp_class_files(sample_cpp_class_ir, tmpdir)
            h_path = os.path.join(tmpdir, "ATestCharacter.h")
            with open(h_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            assert file_content == result[".h"]


class TestGeneratedHeaderStructure:
    """Tests 4-6: Generated .h file structure."""

    def test_contains_pragma_once(self, sample_cpp_class_ir):
        """Test 4: Generated .h contains #pragma once."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert "#pragma once" in result[".h"]

    def test_contains_uclass_macro(self, sample_cpp_class_ir):
        """Test 4: Generated .h contains UCLASS macro."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert "UCLASS(" in result[".h"]

    def test_contains_class_declaration(self, sample_cpp_class_ir):
        """Test 5: Generated .h contains correct class declaration."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        # class ATestCharacter : public ACharacter
        assert "class ATestCharacter" in result[".h"]
        assert ": public ACharacter" in result[".h"]

    def test_contains_generated_body(self, sample_cpp_class_ir):
        """Test 5: Generated .h contains GENERATED_BODY()."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert "GENERATED_BODY()" in result[".h"]

    def test_contains_uproperty_declaration(self, sample_cpp_class_ir):
        """Test 6: Generated .h contains UPROPERTY declarations."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert "UPROPERTY(" in result[".h"]
        # Should contain CameraComp property
        assert "CameraComp" in result[".h"]

    def test_contains_property_type(self, sample_cpp_class_ir):
        """Test 6: Generated .h contains property type declarations."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        # UCameraComponent* CameraComp
        assert "UCameraComponent*" in result[".h"]
        assert "float" in result[".h"]

    def test_contains_method_declaration(self, sample_cpp_class_ir):
        """Test 6: Generated .h contains method declarations."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        # void Aim(float AxisValue)
        assert "void Aim" in result[".h"]
        assert "float AxisValue" in result[".h"]


class TestGeneratedCppStructure:
    """Tests 7-9: Generated .cpp file structure."""

    def test_contains_include_header(self, sample_cpp_class_ir):
        """Test 7: Generated .cpp contains #include for header."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert '#include "ATestCharacter.h"' in result[".cpp"]

    def test_contains_constructor_signature(self, sample_cpp_class_ir):
        """Test 7: Generated .cpp contains constructor signature."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        # ATestCharacter::ATestCharacter()
        assert "ATestCharacter::ATestCharacter()" in result[".cpp"]

    def test_contains_constructor_body(self, sample_cpp_class_ir):
        """Test 7: Generated .cpp contains constructor body."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        assert "{\n" in result[".cpp"] or "{" in result[".cpp"]
        assert "}" in result[".cpp"]

    def test_contains_method_implementation_with_body(self, sample_cpp_class_ir):
        """Test 8: Generated .cpp contains method implementations when body present."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        # void ATestCharacter::Aim(float AxisValue) { ... }
        assert "void ATestCharacter::Aim" in result[".cpp"]
        # Should contain the call statement
        assert "AddControllerPitchInput" in result[".cpp"]

    def test_no_method_impl_for_empty_body(self, sample_cpp_class_ir):
        """Test 9: Empty method.body generates declaration only, no .cpp impl."""
        from uasset_read.agent.writer import write_cpp_class_files
        result = write_cpp_class_files(sample_cpp_class_ir, None)
        # EmptyFunc should NOT have implementation in .cpp
        # It should only appear in .h as declaration
        cpp_content = result[".cpp"]
        # Check that EmptyFunc is in .h but not as implementation in .cpp
        assert "void EmptyFunc" not in cpp_content or cpp_content.count("void EmptyFunc") == 0


class TestCppFileWriterMethods:
    """Test CppFileWriter class methods."""

    def test_generate_header_text(self, sample_cpp_class_ir):
        """Test _generate_header_text returns string."""
        from uasset_read.agent.writer import CppFileWriter
        writer = CppFileWriter(sample_cpp_class_ir)
        header_text = writer._generate_header_text()
        assert isinstance(header_text, str)
        assert "#pragma once" in header_text

    def test_generate_cpp_text(self, sample_cpp_class_ir):
        """Test _generate_cpp_text returns string."""
        from uasset_read.agent.writer import CppFileWriter
        writer = CppFileWriter(sample_cpp_class_ir)
        cpp_text = writer._generate_cpp_text()
        assert isinstance(cpp_text, str)
        assert '#include "ATestCharacter.h"' in cpp_text

    def test_write_to_files_returns_dict(self, sample_cpp_class_ir):
        """Test write_to_files returns dict when output_dir is None."""
        from uasset_read.agent.writer import CppFileWriter
        writer = CppFileWriter(sample_cpp_class_ir)
        result = writer.write_to_files(None)
        assert isinstance(result, dict)
        assert ".h" in result
        assert ".cpp" in result

    def test_write_to_files_writes_to_dir(self, sample_cpp_class_ir):
        """Test write_to_files writes files when output_dir is provided."""
        from uasset_read.agent.writer import CppFileWriter
        writer = CppFileWriter(sample_cpp_class_ir)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = writer.write_to_files(tmpdir)
            h_path = os.path.join(tmpdir, "ATestCharacter.h")
            cpp_path = os.path.join(tmpdir, "ATestCharacter.cpp")
            assert os.path.exists(h_path)
            assert os.path.exists(cpp_path)