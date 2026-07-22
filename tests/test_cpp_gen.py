"""cpp_gen 模块测试 — C++ 头文件、标识符清理、数学简化。"""
from __future__ import annotations

from typing import List

import pytest

from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppClassIR, CppHeaderMeta, CppMethodIR, CppProperty,
)
from uasset_read.cpp_gen.formatters.cpp_header_formatter import format_cpp_header
from uasset_read.cpp_gen.sanitizer import sanitize_identifier
from uasset_read.cpp_gen.math_simplifier import MathSimplifier


def _make_property(
    name: str, cpp_type: str, category: str = "variable",
    marks: List[str] | None = None, default_value=None,
) -> CppProperty:
    if marks is None:
        marks = ["EditAnywhere", "BlueprintReadWrite"]
    return CppProperty(
        cpp_type=cpp_type, name=name, uproperty_marks=marks,
        category=category, default_value=default_value,
    )


def _make_method(
    name: str, return_type: str = "void", parameters: List | None = None,
    specifiers: List[str] | None = None, is_override: bool = False,
    body_text: str | None = None, class_name: str = "", is_static: bool = False,
) -> CppMethodIR:
    if parameters is None:
        parameters = []
    if specifiers is None:
        specifiers = ["BlueprintCallable"]
    return CppMethodIR(
        cpp_name=name, return_type=return_type, parameters=parameters,
        ufunction_specifiers=specifiers, is_override=is_override,
        body_text=body_text, class_name=class_name, is_static=is_static,
    )


def _build_actor_blueprint_ir() -> CppClassIR:
    properties = [
        _make_property("Mesh", "UStaticMeshComponent*", category="component",
                       marks=["VisibleAnywhere", "BlueprintReadOnly", "Instanced"]),
        _make_property("MoveSpeed", "float", default_value=600.0),
    ]
    methods = [
        _make_method("ReceiveBeginPlay", body_text="// custom logic"),
    ]
    return CppClassIR(
        name="AMyActor_C",
        parent_class="AActor",
        properties=properties,
        methods=methods,
        header_meta=CppHeaderMeta(),
    )


class TestCppHeader:
    def test_blueprint_cpp_header(self):
        """头文件应包含 UCLASS、UPROPERTY、UFUNCTION 宏。"""
        ir = _build_actor_blueprint_ir()
        header = format_cpp_header(ir)
        assert "UCLASS" in header
        assert "UPROPERTY" in header
        assert "UFUNCTION" in header


class TestSanitizeIdentifier:
    def test_spaces_to_underscores(self):
        assert sanitize_identifier("hello world") == "hello_world"

    def test_digit_prefix(self):
        assert sanitize_identifier("123abc") == "_123abc"


class TestMathSimplifier:
    def test_add_int_simplification(self):
        """Add_IntInt 应简化为 +。"""
        simplifier = MathSimplifier()
        assert simplifier.simplify("Add_IntInt") == "+"
