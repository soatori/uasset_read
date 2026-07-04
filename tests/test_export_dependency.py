"""ExportDependencyIR 数据结构测试。"""

from __future__ import annotations

import pytest

from uasset_read.models.ir import ExportDependencyIR


def test_export_dependency_ir_basic():
    """测试 ExportDependencyIR 基本创建和字段访问"""
    ir = ExportDependencyIR(
        export_index=0,
        serialization_before_serialization=[1, 2],
        create_before_serialization=[3],
        serialization_before_create=[],
        create_before_create=[4]
    )
    assert ir.export_index == 0
    assert len(ir.serialization_before_serialization) == 2
    assert ir.serialization_before_serialization == [1, 2]
    assert ir.create_before_serialization == [3]
    assert ir.serialization_before_create == []
    assert ir.create_before_create == [4]


def test_export_dependency_ir_empty_dependencies():
    """测试所有依赖列表为空的情况"""
    ir = ExportDependencyIR(
        export_index=5,
        serialization_before_serialization=[],
        create_before_serialization=[],
        serialization_before_create=[],
        create_before_create=[]
    )
    assert ir.export_index == 5
    assert len(ir.serialization_before_serialization) == 0
    assert len(ir.create_before_serialization) == 0
    assert len(ir.serialization_before_create) == 0
    assert len(ir.create_before_create) == 0


def test_export_dependency_ir_multiple_dependencies():
    """测试多个依赖的情况"""
    ir = ExportDependencyIR(
        export_index=10,
        serialization_before_serialization=[0, 1, 2, 3],
        create_before_serialization=[4, 5],
        serialization_before_create=[6, 7, 8],
        create_before_create=[9]
    )
    assert ir.export_index == 10
    assert len(ir.serialization_before_serialization) == 4
    assert len(ir.create_before_serialization) == 2
    assert len(ir.serialization_before_create) == 3
    assert len(ir.create_before_create) == 1
