"""P2 LWC 门控测试 — Kismet 字节码版本感知 (#98)。"""
from __future__ import annotations

import struct
from unittest.mock import Mock
from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions.vector_consts import (
    EX_VectorConst,
    EX_RotationConst,
    EX_TransformConst,
)


def test_fkismetarchive_accepts_version():
    """FKismetArchive 构造函数应接受 file_version_ue5 参数。"""
    archive = FKismetArchive(
        data=b"\x00" * 100,
        name="test",
        name_map=["test"],
        file_version_ue5=1004,
    )
    assert archive.file_version_ue5 == 1004


def test_is_lwc_property():
    """is_lwc 属性应基于版本号返回正确值。"""
    # Pre-LWC
    archive = FKismetArchive(b"\x00" * 100, "test", ["test"], file_version_ue5=1000)
    assert archive.is_lwc is False

    # LWC
    archive = FKismetArchive(b"\x00" * 100, "test", ["test"], file_version_ue5=1004)
    assert archive.is_lwc is True

    # Later version
    archive = FKismetArchive(b"\x00" * 100, "test", ["test"], file_version_ue5=1010)
    assert archive.is_lwc is True


def test_vector_const_pre_lwc():
    """Pre-LWC: VectorConst 读取 3 × float32 = 12 bytes。"""
    data = struct.pack('<fff', 1.0, 2.0, 3.0)
    archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1000)
    expr = EX_VectorConst.from_archive(archive, ["test"])
    assert expr.X == 1.0
    assert expr.Y == 2.0
    assert expr.Z == 3.0


def test_vector_const_lwc():
    """LWC: VectorConst 读取 3 × float64 = 24 bytes。"""
    data = struct.pack('<ddd', 1.5, 2.5, 3.5)
    archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1004)
    expr = EX_VectorConst.from_archive(archive, ["test"])
    assert expr.X == 1.5
    assert expr.Y == 2.5
    assert expr.Z == 3.5


def test_rotation_const_pre_lwc():
    """Pre-LWC: RotationConst 读取 3 × int32 = 12 bytes。"""
    data = struct.pack('<iii', 90, 180, 270)
    archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1000)
    expr = EX_RotationConst.from_archive(archive, ["test"])
    assert expr.Pitch == 90
    assert expr.Yaw == 180
    assert expr.Roll == 270


def test_rotation_const_lwc():
    """LWC: RotationConst 读取 3 × int64 = 24 bytes。"""
    data = struct.pack('<qqq', 90000, 180000, 270000)
    archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1004)
    expr = EX_RotationConst.from_archive(archive, ["test"])
    assert expr.Pitch == 90000
    assert expr.Yaw == 180000
    assert expr.Roll == 270000


def test_transform_const_pre_lwc():
    """Pre-LWC: TransformConst 读取 10 × float32 = 40 bytes。"""
    # Rotation (4) + Translation (3) + Scale (3)
    data = struct.pack('<ffff', 0.0, 0.0, 0.0, 1.0)  # rotation
    data += struct.pack('<fff', 1.0, 2.0, 3.0)  # translation
    data += struct.pack('<fff', 1.0, 1.0, 1.0)  # scale
    archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1000)
    expr = EX_TransformConst.from_archive(archive, ["test"])
    # Pitch/Yaw/Roll 是平移分量的字段名
    assert expr.Pitch == 1.0
    assert expr.Yaw == 2.0
    assert expr.Roll == 3.0


def test_transform_const_lwc():
    """LWC: TransformConst 读取 4×float32 + 3×float64 + 3×float32 = 52 bytes。"""
    # Rotation (4 × float32)
    data = struct.pack('<ffff', 0.0, 0.0, 0.0, 1.0)
    # Translation (3 × float64)
    data += struct.pack('<ddd', 10.5, 20.5, 30.5)
    # Scale (3 × float32)
    data += struct.pack('<fff', 2.0, 2.0, 2.0)
    archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1004)
    expr = EX_TransformConst.from_archive(archive, ["test"])
    # Pitch/Yaw/Roll 是平移分量的字段名，SX/SY/SZ 是缩放分量
    assert expr.Pitch == 10.5
    assert expr.Yaw == 20.5
    assert expr.Roll == 30.5
    assert expr.SX == 2.0
