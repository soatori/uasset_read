"""StructProperty Transform 解析测试 — 修正大小常量和读取逻辑 (#329)"""

import struct
import pytest
from unittest.mock import MagicMock


def test_transform_size_f32():
    """FTransform3f 大小应为 40 字节。"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # 当前值为 48，应为 40
    assert _EXPECTED_STRUCT_SIZES.get("Transform") == 40


def test_transform_size_lwc():
    """Transform LWC 映射应为 (40, 80)。"""
    from uasset_read.parsers.property_types import _LWC_TYPE_MAP
    # 当前值为 (48, 48)，应为 (40, 80)
    assert _LWC_TYPE_MAP.get("Transform") == (40, 80)


def test_transform3f_size():
    """Transform3f 紧凑格式大小应为 40 字节。"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Transform3f") == 40


def test_transform_read_f32():
    """FTransform3f 应正确读取 40 字节。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct

    # 构造 40 字节的 FTransform3f 数据
    # Rotation: 4 * float (16 bytes)
    # Translation: 3 * float (12 bytes)
    # Scale3D: 3 * float (12 bytes)
    data = struct.pack('<10f',
        0.0, 0.0, 0.0, 1.0,  # Rotation (x, y, z, w)
        100.0, 200.0, 300.0,  # Translation (x, y, z)
        1.0, 1.0, 1.0         # Scale3D (x, y, z)
    )
    archive = ByteArchive(data)

    # 创建 mock PropertyTag
    tag = MagicMock()
    tag.size = 40
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result is not None
    assert result.struct_type == "Transform"
    assert result.fields["Translation"]["X"] == 100.0
    assert result.fields["Translation"]["Y"] == 200.0
    assert result.fields["Translation"]["Z"] == 300.0
    assert result.fields["Rotation"]["W"] == 1.0
    assert result.fields["Scale3D"]["X"] == 1.0
    assert result.fields["Scale3D"]["Y"] == 1.0
    assert result.fields["Scale3D"]["Z"] == 1.0


def test_transform_read_f64():
    """FTransform3d 应正确读取 80 字节。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct

    # 构造 80 字节的 FTransform3d 数据
    # Rotation: 4 * double (32 bytes)
    # Translation: 3 * double (24 bytes)
    # Scale3D: 3 * double (24 bytes)
    data = struct.pack('<10d',
        0.0, 0.0, 0.0, 1.0,  # Rotation (x, y, z, w)
        100.0, 200.0, 300.0,  # Translation (x, y, z)
        1.0, 1.0, 1.0         # Scale3D (x, y, z)
    )
    archive = ByteArchive(data)

    # 创建 mock PropertyTag
    tag = MagicMock()
    tag.size = 80
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result is not None
    assert result.struct_type == "Transform"
    assert result.fields["Translation"]["X"] == 100.0
    assert result.fields["Translation"]["Y"] == 200.0
    assert result.fields["Translation"]["Z"] == 300.0
    assert result.fields["Rotation"]["W"] == 1.0
    assert result.fields["Scale3D"]["X"] == 1.0
    assert result.fields["Scale3D"]["Y"] == 1.0
    assert result.fields["Scale3D"]["Z"] == 1.0


def test_transform_read_unexpected_size():
    """非标准大小的 Transform 在 tolerant 模式下应跳过并返回警告。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct

    # 构造 52 字节的数据（非标准大小）
    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,   # Rotation
        10.0, 20.0, 30.0,     # Translation
        100.0, 200.0, 300.0   # Scale3D
    )
    archive = ByteArchive(data, tolerant=True)  # 设置为 tolerant 模式

    # 创建 mock PropertyTag
    tag = MagicMock()
    tag.size = 52
    tag.struct_type = "Transform"

    # tolerant 模式：返回带 _warning 的 StructValue
    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])
    assert result is not None
    assert result.struct_type == "Transform"
    assert "_warning" in result.fields
    assert "52" in result.fields["_warning"]


def test_transform_read_unexpected_size_strict():
    """非标准大小的 Transform 在 strict 模式下应抛出 ParseError。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct
    from uasset_read.exceptions import ParseError

    # 构造 52 字节的数据（非标准大小）
    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,   # Rotation
        10.0, 20.0, 30.0,     # Translation
        100.0, 200.0, 300.0   # Scale3D
    )
    archive = ByteArchive(data)
    archive._tolerant = False  # 设置为 strict 模式

    tag = MagicMock()
    tag.size = 52
    tag.struct_type = "Transform"

    with pytest.raises(ParseError, match="unexpected size 52"):
        _try_fast_path_struct("Transform", tag, archive, name_map=[])


def test_transform_serialization_order():
    """验证 Transform 序列化顺序：Rotation → Translation → Scale3D。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct

    # 使用明确可区分的值来验证顺序
    # Rotation: (1.0, 2.0, 3.0, 4.0) = 16 bytes
    # Translation: (10.0, 20.0, 30.0) = 12 bytes
    # Scale3D: (100.0, 200.0, 300.0) = 12 bytes
    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,   # Rotation
        10.0, 20.0, 30.0,     # Translation
        100.0, 200.0, 300.0   # Scale3D
    )
    archive = ByteArchive(data)

    tag = MagicMock()
    tag.size = 40
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result.fields["Rotation"]["X"] == 1.0
    assert result.fields["Rotation"]["W"] == 4.0
    assert result.fields["Translation"]["X"] == 10.0
    assert result.fields["Translation"]["Z"] == 30.0
    assert result.fields["Scale3D"]["X"] == 100.0
    assert result.fields["Scale3D"]["Z"] == 300.0
