"""
DependsMap 异常数量防护测试 (#336)。
验证畸形的 DependsMap 数据不会导致解析中断，而是优雅跳过异常条目。
"""
import struct
import pytest
from uasset_read.archive import ByteArchive
from uasset_read.serializers.package_summary import read_depends_map, PackageFileSummary


# depends_offset 必须 > 0（函数入口检查），但 ByteArchive 会 seek 到该位置
# 所以数据需要在 offset=1 处开始，前 1 字节是填充
_PADDING = b'\x00'


def _make_summary(export_count: int, depends_offset: int = 1) -> PackageFileSummary:
    """创建用于测试的最小化 PackageFileSummary。"""
    summary = PackageFileSummary.__new__(PackageFileSummary)
    summary.depends_offset = depends_offset
    summary.export_count = export_count
    return summary


def _i32_le(value: int) -> bytes:
    """将 int32 编码为小端字节序列。"""
    return struct.pack('<i', value)


def test_depends_map_abnormal_count():
    """DependsMap 异常数量（>10000）应跳过该条目，返回空列表。"""
    # dep_count = 100000 (超出 10000 限制)
    data = _PADDING + _i32_le(100000)

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert result == [[]], "异常数量条目应跳过，返回空列表"


def test_depends_map_negative_count():
    """DependsMap 负数数量应跳过该条目。"""
    data = _PADDING + _i32_le(-1)

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert result == [[]], "负数数量条目应跳过，返回空列表"


def test_depends_map_boundary_count():
    """DependsMap 边界值（正好 10000）应正常解析。"""
    # dep_count = 10000, 后续跟 10000 个 i32 依赖值（全为 0）
    dep_count_bytes = _i32_le(10000)
    deps_bytes = _i32_le(0) * 10000
    data = _PADDING + dep_count_bytes + deps_bytes

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert len(result) == 1
    assert len(result[0]) == 10000


def test_depends_map_mixed_normal_and_abnormal():
    """混合正常和异常条目时，仅跳过异常条目。"""
    # export_count = 3
    # 条目 0: dep_count = 2 (正常) → 两个依赖值 0, 0
    # 条目 1: dep_count = 50000 (异常) → 跳过
    # 条目 2: dep_count = 1 (正常) → 一个依赖值 0
    data = (
        _PADDING
        + _i32_le(2)       # dep_count = 2
        + _i32_le(0) * 2   # 2 deps
        + _i32_le(50000)   # dep_count = 50000 (异常)
        + _i32_le(1)       # dep_count = 1
        + _i32_le(0)       # 1 dep
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=3)

    result = read_depends_map(archive, summary)
    assert len(result) == 3, "应返回 3 个条目"
    assert len(result[0]) == 2, "条目 0 应有 2 个依赖"
    assert result[1] == [], "条目 1（异常）应被跳过"
    assert len(result[2]) == 1, "条目 2 应有 1 个依赖"


def test_depends_map_empty():
    """DependsMap 无数据时返回空列表。"""
    summary = _make_summary(export_count=0, depends_offset=0)

    result = read_depends_map(ByteArchive(b''), summary)
    assert result == []


def test_depends_map_zero_offset():
    """DependsMap offset 为 0 时返回空列表。"""
    summary = _make_summary(export_count=5, depends_offset=0)
    result = read_depends_map(ByteArchive(b'\x00' * 100), summary)
    assert result == []
