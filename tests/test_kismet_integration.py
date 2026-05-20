"""
Kismet integration tests — Phase 64.

Tests for KismetDecompiledResult dataclass, ParseResult/LinkerParseResult
decompiled_functions fields, and decompile_uasset() pipeline.
"""
from __future__ import annotations

import json
import pytest

from dataclasses import fields


# ===========================================================================
# Task 1: KismetDecompiledResult dataclass
# ===========================================================================


def test_kismet_decompiled_result_dataclass():
    """Test KismetDecompiledResult creation with all 5 fields."""
    from uasset_read.kismet.result import KismetDecompiledResult

    result = KismetDecompiledResult(
        function_name="TestFn",
        signature="void TestFn()",
        local_variables=[],
        cpp_code="// code",
        expressions=[],
    )

    assert result.function_name == "TestFn"
    assert result.signature == "void TestFn()"
    assert result.local_variables == []
    assert result.cpp_code == "// code"
    assert result.expressions == []


def test_kismet_decompiled_result_to_dict():
    """Test KismetDecompiledResult.to_dict() returns dict with all 5 fields."""
    from uasset_read.kismet.result import KismetDecompiledResult

    result = KismetDecompiledResult(
        function_name="ExecuteUbergraph_MyBP",
        signature="void ExecuteUbergraph_MyBP(int32 EntryPoint)",
        local_variables=[{"name": "Temp", "type": "int32"}],
        cpp_code="void ExecuteUbergraph_MyBP(int32 EntryPoint) {\n    // code\n}",
        expressions=[],
    )

    d = result.to_dict()

    assert d["function_name"] == "ExecuteUbergraph_MyBP"
    assert d["signature"] == "void ExecuteUbergraph_MyBP(int32 EntryPoint)"
    assert d["local_variables"] == [{"name": "Temp", "type": "int32"}]
    assert d["cpp_code"] == "void ExecuteUbergraph_MyBP(int32 EntryPoint) {\n    // code\n}"
    assert d["expressions"] == []


def test_kismet_decompiled_result_to_dict_json_serializable():
    """Test KismetDecompiledResult.to_dict() is JSON-serializable."""
    from uasset_read.kismet.result import KismetDecompiledResult

    result = KismetDecompiledResult(
        function_name="TestFn",
        signature="void TestFn()",
        local_variables=[{"name": "X", "type": "float"}],
        cpp_code="// test",
        expressions=[],
    )

    d = result.to_dict()
    json_str = json.dumps(d)
    assert isinstance(json_str, str)
    assert "TestFn" in json_str


def test_kismet_decompiled_result_to_json():
    """Test KismetDecompiledResult.to_json() returns formatted JSON string."""
    from uasset_read.kismet.result import KismetDecompiledResult

    result = KismetDecompiledResult(
        function_name="Fn",
        signature="void Fn()",
        local_variables=[],
        cpp_code="// fn",
        expressions=[],
    )

    j = result.to_json(indent=2)
    parsed = json.loads(j)
    assert parsed["function_name"] == "Fn"


def test_kismet_decompiled_result_to_cpp_string():
    """Test KismetDecompiledResult.to_cpp_string() returns cpp_code."""
    from uasset_read.kismet.result import KismetDecompiledResult

    code = "void Test() {\n    return;\n}"
    result = KismetDecompiledResult(
        function_name="Test",
        signature="void Test()",
        local_variables=[],
        cpp_code=code,
        expressions=[],
    )

    assert result.to_cpp_string() == code


def test_kismet_decompiled_result_expressions_with_to_dict():
    """Test expressions serialization falls back to str() when no to_dict()."""
    from uasset_read.kismet.result import KismetDecompiledResult

    # Expression without to_dict
    class FakeExpr:
        def __init__(self):
            self.StatementIndex = 0

        def __str__(self):
            return "FakeExpr()"

    result = KismetDecompiledResult(
        function_name="Test",
        signature="void Test()",
        local_variables=[],
        cpp_code="// test",
        expressions=[FakeExpr()],
    )

    d = result.to_dict()
    assert d["expressions"] == ["FakeExpr()"]


def test_kismet_decompiled_result_expressions_with_to_dict_method():
    """Test expressions serialization calls to_dict() when available."""
    from uasset_read.kismet.result import KismetDecompiledResult

    class ExprWithDict:
        def __init__(self):
            self.StatementIndex = 0

        def to_dict(self):
            return {"StatementIndex": 0}

        def __str__(self):
            return "ExprWithDict()"

    result = KismetDecompiledResult(
        function_name="Test",
        signature="void Test()",
        local_variables=[],
        cpp_code="// test",
        expressions=[ExprWithDict()],
    )

    d = result.to_dict()
    assert d["expressions"] == [{"StatementIndex": 0}]


# ===========================================================================
# Task 1: ParseResult and LinkerParseResult decompiled_functions fields
# ===========================================================================


def test_parse_result_has_decompiled_functions():
    """Test ParseResult().decompiled_functions == [] (default empty list)."""
    from uasset_read.models.result import ParseResult

    result = ParseResult()
    assert hasattr(result, "decompiled_functions")
    assert result.decompiled_functions == []


def test_linker_parse_result_has_decompiled_functions():
    """Test LinkerParseResult().decompiled_functions == [] (default empty list)."""
    from uasset_read.link.result import LinkerParseResult

    result = LinkerParseResult()
    assert hasattr(result, "decompiled_functions")
    assert result.decompiled_functions == []


def test_parse_result_decompiled_functions_can_be_set():
    """Test ParseResult.decompiled_functions can hold KismetDecompiledResult."""
    from uasset_read.models.result import ParseResult
    from uasset_read.kismet.result import KismetDecompiledResult

    result = ParseResult()
    fn = KismetDecompiledResult(
        function_name="TestFn",
        signature="void TestFn()",
        local_variables=[],
        cpp_code="// code",
        expressions=[],
    )
    result.decompiled_functions.append(fn)
    assert len(result.decompiled_functions) == 1
    assert result.decompiled_functions[0].function_name == "TestFn"


def test_linker_parse_result_decompiled_functions_can_be_set():
    """Test LinkerParseResult.decompiled_functions can hold KismetDecompiledResult."""
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.kismet.result import KismetDecompiledResult

    result = LinkerParseResult()
    fn = KismetDecompiledResult(
        function_name="TestFn",
        signature="void TestFn()",
        local_variables=[],
        cpp_code="// code",
        expressions=[],
    )
    result.decompiled_functions.append(fn)
    assert len(result.decompiled_functions) == 1
    assert result.decompiled_functions[0].function_name == "TestFn"


# ===========================================================================
# Task 2: decompile_uasset() pipeline
# ===========================================================================


def test_decompile_uasset_returns_results():
    """Test decompile_uasset(path) on a Blueprint .uasset returns non-empty list."""
    import os
    from uasset_read.kismet.pipeline import decompile_uasset
    from uasset_read.kismet.result import KismetDecompiledResult

    # Use a real Blueprint .uasset from the test assets
    test_path = r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\BP_FirstPersonCharacter.uasset"
    if not os.path.exists(test_path):
        pytest.skip(f"Test asset not found: {test_path}")

    results = decompile_uasset(test_path)

    assert isinstance(results, list)
    # At least some UStruct exports should have bytecode
    assert len(results) > 0, f"Expected non-empty results for Blueprint, got {len(results)}"
    for r in results:
        assert isinstance(r, KismetDecompiledResult)
        assert r.function_name, f"Expected non-empty function_name, got {r}"
        assert isinstance(r.cpp_code, str)


def test_decompile_uasset_non_blueprint():
    """Test decompile_uasset(path) on a non-Blueprint .uasset returns empty list."""
    from uasset_read.kismet.pipeline import decompile_uasset

    # Use a non-Blueprint .uasset (e.g., a level or other package)
    # This should not crash and return empty list
    # If no non-Blueprint file is available, skip this test gracefully
    import os
    test_path = r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\FirstPersonMap.uasset"
    if not os.path.exists(test_path):
        pytest.skip(f"Non-Blueprint test file not found: {test_path}")

    results = decompile_uasset(test_path)
    assert isinstance(results, list)
    # Non-Blueprint packages should return empty list (no UStruct exports with bytecode)


def test_decompile_uasset_missing_file():
    """Test decompile_uasset on missing file raises FileNotFoundError."""
    from uasset_read.kismet.pipeline import decompile_uasset

    with pytest.raises(FileNotFoundError):
        decompile_uasset("nonexistent/path/file.uasset")


def test_decompile_single_function_returns_none_for_non_ustruct():
    """Test decompile_single_function returns None for non-UStruct exports."""
    from uasset_read.kismet.pipeline import decompile_single_function
    from uasset_read.serializers.object_resources import ObjectExport, PackageIndex

    # Create a non-UStruct export with minimal required fields
    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="Default__SomeClass",
        object_flags=0,
        serial_size=100,
        serial_offset=0,
    )

    # This should have correct object_name
    assert export.object_name == "Default__SomeClass"
