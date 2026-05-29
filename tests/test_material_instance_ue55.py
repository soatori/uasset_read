"""UE5.5 MaterialInstance 解析测试"""
from __future__ import annotations

import struct
from pathlib import Path

from uasset_read.archive import FArchive
from uasset_read.parsers.asset_types.material_instance import (
    parse_material_instance,
    MAX_PARAM_COUNT,
)


def _make_archive(tmp_path: Path, data: bytes) -> FArchive:
    """从字节数据创建临时文件并返回 FArchive 实例。"""
    path = tmp_path / "test_material.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=True)


# ---------- 基本解析测试 ----------

def test_material_instance_basic(tmp_path):
    """MaterialInstance 基本解析：标量 + 向量 + 纹理各一个参数。"""
    name_map = ["", "ParentMaterial", "ScalarParam", "VectorParam", "TextureParam"]

    # parent_material_index = 1
    data = struct.pack('<i', 1)
    # scalar_count = 1, (name_idx=2, value=0.5)
    data += struct.pack('<i', 1)
    data += struct.pack('<i', 2)
    data += struct.pack('<f', 0.5)
    # vector_count = 1, (name_idx=3, RGBA)
    data += struct.pack('<i', 1)
    data += struct.pack('<i', 3)
    data += struct.pack('<ffff', 1.0, 0.0, 0.0, 1.0)
    # texture_count = 1, (name_idx=4, texture_idx=0)
    data += struct.pack('<i', 1)
    data += struct.pack('<i', 4)
    data += struct.pack('<i', 0)

    archive = _make_archive(tmp_path, data)
    try:
        result = parse_material_instance(archive, name_map)

        assert "parse_error" not in result
        assert result["parent_material_index"] == 1
        assert result["scalar_overrides"]["ScalarParam"] == 0.5
        assert result["vector_overrides"]["VectorParam"] == (1.0, 0.0, 0.0, 1.0)
        assert result["texture_overrides"]["TextureParam"] == 0
        assert result["override_count"] == 3
    finally:
        archive.close()


# ---------- 零参数测试 ----------

def test_material_instance_no_overrides(tmp_path):
    """所有参数计数为零，应正常返回空覆盖字典。"""
    name_map = ["", "ParentMaterial"]

    data = struct.pack('<i', 1)   # parent_material_index
    data += struct.pack('<i', 0)  # scalar_count = 0
    data += struct.pack('<i', 0)  # vector_count = 0
    data += struct.pack('<i', 0)  # texture_count = 0

    archive = _make_archive(tmp_path, data)
    try:
        result = parse_material_instance(archive, name_map)

        assert "parse_error" not in result
        assert result["scalar_overrides"] == {}
        assert result["vector_overrides"] == {}
        assert result["texture_overrides"] == {}
        assert result["override_count"] == 0
    finally:
        archive.close()


# ---------- 边界检查测试 ----------

def test_material_instance_negative_scalar_count(tmp_path):
    """scalar_count 为负数时应捕获异常并设置 parse_error。"""
    name_map = ["", "ParentMaterial"]

    data = struct.pack('<i', 1)    # parent_material_index
    data += struct.pack('<i', -5)  # scalar_count = -5 (无效)
    data += struct.pack('<i', 0)   # vector_count = 0
    data += struct.pack('<i', 0)   # texture_count = 0

    archive = _make_archive(tmp_path, data)
    try:
        result = parse_material_instance(archive, name_map)

        assert "parse_error" in result
    finally:
        archive.close()


def test_material_instance_huge_count(tmp_path):
    """计数超过 MAX_PARAM_COUNT 时应捕获异常并设置 parse_error。"""
    name_map = ["", "ParentMaterial"]

    data = struct.pack('<i', 1)                        # parent_material_index
    data += struct.pack('<i', MAX_PARAM_COUNT + 100)   # scalar_count too large
    data += struct.pack('<i', 0)                        # vector_count
    data += struct.pack('<i', 0)                        # texture_count

    archive = _make_archive(tmp_path, data)
    try:
        result = parse_material_instance(archive, name_map)

        assert "parse_error" in result
    finally:
        archive.close()


# ---------- 异常数据处理测试 ----------

def test_material_instance_invalid_name_index(tmp_path):
    """名称索引超出 name_map 范围时应使用 fallback 名称。"""
    name_map = ["", "ParentMaterial"]

    data = struct.pack('<i', 1)  # parent_material_index
    # scalar_count = 1, name_idx = 999 (超出范围), value = 1.0
    data += struct.pack('<i', 1)
    data += struct.pack('<i', 999)
    data += struct.pack('<f', 1.0)
    data += struct.pack('<i', 0)  # vector_count
    data += struct.pack('<i', 0)  # texture_count

    archive = _make_archive(tmp_path, data)
    try:
        result = parse_material_instance(archive, name_map)

        assert "parse_error" not in result
        assert "param_999" in result["scalar_overrides"]
        assert result["scalar_overrides"]["param_999"] == 1.0
    finally:
        archive.close()


def test_material_instance_negative_name_index(tmp_path):
    """名称索引为负数时应使用 fallback 名称。"""
    name_map = ["", "ParentMaterial"]

    data = struct.pack('<i', 1)  # parent_material_index
    # scalar_count = 1, name_idx = -1 (无效), value = 2.0
    data += struct.pack('<i', 1)
    data += struct.pack('<i', -1)
    data += struct.pack('<f', 2.0)
    data += struct.pack('<i', 0)  # vector_count
    data += struct.pack('<i', 0)  # texture_count

    archive = _make_archive(tmp_path, data)
    try:
        result = parse_material_instance(archive, name_map)

        assert "parse_error" not in result
        assert "param_-1" in result["scalar_overrides"]
    finally:
        archive.close()


# ---------- 数据截断测试 ----------

def test_material_instance_truncated_data(tmp_path):
    """数据在读取中途截断时应捕获异常并设置 parse_error。"""
    name_map = ["", "ParentMaterial"]

    # 标量计数为 2，但实际只写了一个参数的数据
    data = struct.pack('<i', 1)  # parent_material_index
    data += struct.pack('<i', 2)  # scalar_count = 2
    data += struct.pack('<i', 1)  # 第一个参数的 name_idx
    data += struct.pack('<f', 1.0)  # 第一个参数的 value
    # 缺少第二个参数的数据

    archive = _make_archive(tmp_path, data)
    try:
        result = parse_material_instance(archive, name_map)

        # 应捕获异常而不是抛出
        assert "parse_error" in result
    finally:
        archive.close()
