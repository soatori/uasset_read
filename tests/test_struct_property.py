"""
StructProperty fast-path 单元测试 — Phase 76 COR-01.

覆盖新增 fast-path struct 类型的 raw read 逻辑：
Vector4, LinearColor, Color, Quat, Plane, Guid, IntPoint, IntVector,
Box2D, Box, Sphere, BoxSphereBounds, Matrix, TwoVectors, OrientedBox,
Transform (LWC double).
"""

import io
import struct
import pytest

from uasset_read.archive import FArchive
from uasset_read.parsers.property_types import parse_struct_property
from uasset_read.models.properties import PropertyTag, StructValue


class _MockArchive(FArchive):
    """FArchive 包装器，直接用二进制数据初始化，跳过文件打开。"""
    def __init__(self, data: bytes):
        self._file = io.BytesIO(data)
        self._byte_swapping = False
        self._path = "<mock>"
        self._tolerant = True
        self._use_mmap = False
        self._mmap = None
        self._file_size = len(data)

    def close(self):
        self._file.close()


def _make_tag(struct_type: str, size: int = 0) -> PropertyTag:
    """Create a PropertyTag where _extract_struct_type_from_tag returns the given struct_type.

    Real format: 'StructProperty(Vector)' → extracts 'Vector'.
    """
    return PropertyTag(
        name="TestProp",
        type=f"StructProperty({struct_type})",
        size=size,
        array_index=0,
        flags=0,
        bool_val=0,
        property_guid=None,
        override_operation=None,
        experimental_overridable_logic=None,
        enum_type=None,
        tag_start_offset=None,
        value_start_offset=None,
        value_end_offset=None,
    )


class TestVector4FastPath:
    def test_vector4(self):
        data = struct.pack("<4f", 1.0, 2.0, 3.0, 4.0)
        archive = _MockArchive(data)
        tag = _make_tag("Vector4")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Vector4"
        assert result.fields["X"] == 1.0
        assert result.fields["Y"] == 2.0
        assert result.fields["Z"] == 3.0
        assert result.fields["W"] == 4.0


class TestQuatFastPath:
    def test_quat(self):
        data = struct.pack("<4f", 0.0, 0.0, 0.7071, 0.7071)
        archive = _MockArchive(data)
        tag = _make_tag("Quat")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Quat"
        assert result.fields["X"] == 0.0
        assert result.fields["W"] == pytest.approx(0.7071)


class TestPlaneFastPath:
    def test_plane(self):
        data = struct.pack("<4f", 0.0, 1.0, 0.0, -5.0)
        archive = _MockArchive(data)
        tag = _make_tag("Plane")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Plane"
        assert result.fields["W"] == -5.0


class TestGuidFastPath:
    def test_guid(self):
        data = struct.pack("<4I", 0xAABBCCDD, 0x11223344, 0x55667788, 0x99AABBCC)
        archive = _MockArchive(data)
        tag = _make_tag("Guid")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Guid"
        assert result.fields["A"] == 0xAABBCCDD
        assert result.fields["D"] == 0x99AABBCC


class TestIntPointFastPath:
    def test_intpoint(self):
        data = struct.pack("<2i", 100, 200)
        archive = _MockArchive(data)
        tag = _make_tag("IntPoint")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "IntPoint"
        assert result.fields["X"] == 100
        assert result.fields["Y"] == 200


class TestIntVectorFastPath:
    def test_intvector(self):
        data = struct.pack("<3i", 1, 2, 3)
        archive = _MockArchive(data)
        tag = _make_tag("IntVector")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "IntVector"
        assert result.fields["Z"] == 3


class TestBoxFastPath:
    def test_box(self):
        data = struct.pack("<6fi", 0, 0, 0, 10, 10, 10, 1)
        archive = _MockArchive(data)
        tag = _make_tag("Box")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Box"
        assert result.fields["Min"]["X"] == 0
        assert result.fields["Max"]["Z"] == 10
        assert result.fields["bIsValid"] is True


class TestBox2DFastPath:
    def test_box2d(self):
        data = struct.pack("<4fi", 0, 0, 5, 5, 1)
        archive = _MockArchive(data)
        tag = _make_tag("Box2D")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Box2D"
        assert result.fields["Min"]["Y"] == 0
        assert result.fields["bIsValid"] is True


class TestSphereFastPath:
    def test_sphere(self):
        data = struct.pack("<4f", 1, 2, 3, 10.5)
        archive = _MockArchive(data)
        tag = _make_tag("Sphere")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Sphere"
        assert result.fields["Center"]["X"] == 1
        assert result.fields["W"] == 10.5


class TestBoxSphereBoundsFastPath:
    def test_box_sphere_bounds(self):
        # Origin(3f) + BoxExtent(3f) + SphereRadius(1f)
        data = struct.pack("<7f", 0, 0, 0, 50, 50, 50, 86.6)
        archive = _MockArchive(data)
        tag = _make_tag("BoxSphereBounds")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "BoxSphereBounds"
        assert result.fields["Origin"]["Z"] == 0
        assert result.fields["SphereRadius"] == pytest.approx(86.6)


class TestMatrixFastPath:
    def test_matrix(self):
        values = [float(i) for i in range(16)]
        data = struct.pack("<16f", *values)
        archive = _MockArchive(data)
        tag = _make_tag("Matrix")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Matrix"
        assert len(result.fields["M"]) == 4
        assert len(result.fields["M"][0]) == 4
        assert result.fields["M"][0][0] == 0.0
        assert result.fields["M"][3][3] == 15.0


class TestTwoVectorsFastPath:
    def test_two_vectors(self):
        data = struct.pack("<6f", 1, 2, 3, 4, 5, 6)
        archive = _MockArchive(data)
        tag = _make_tag("TwoVectors")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "TwoVectors"
        assert result.fields["E1"]["Z"] == 3
        assert result.fields["E2"]["X"] == 4


class TestOrientedBoxFastPath:
    def test_oriented_box(self):
        # 3 axes (9f) + extent (3f) + center (3f) = 15 floats
        data = struct.pack("<15f", *(float(i) for i in range(15)))
        archive = _MockArchive(data)
        tag = _make_tag("OrientedBox")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "OrientedBox"
        assert result.fields["AxisX"]["X"] == 0.0
        assert result.fields["Center"]["Z"] == 14.0


class TestTransformFastPathLWC:
    """Transform in UE5 uses double for FVector (LWC)."""

    def test_transform_double_translation(self):
        # Translation: 3x f64, Rotation: 4x f32, Scale: 3x f32
        data = struct.pack("<3d4f3f",
            1.5, 2.5, 3.5,   # Translation (double)
            0, 0, 0, 1,       # Rotation (quat, float)
            1, 1, 1,          # Scale (float)
        )
        archive = _MockArchive(data)
        tag = _make_tag("Transform")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Transform"
        assert result.fields["Translation"]["Y"] == 2.5
        assert result.fields["Rotation"]["W"] == 1.0
        assert result.fields["Scale3D"]["X"] == 1.0


class TestColorFastPath:
    def test_color(self):
        # Color: 4x u8 (B, G, R, A)
        data = struct.pack("<4B", 255, 128, 64, 200)
        archive = _MockArchive(data)
        tag = _make_tag("Color")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Color"
        assert result.fields["R"] == 64
        assert result.fields["A"] == 200


class TestLinearColorFastPath:
    def test_linear_color(self):
        data = struct.pack("<4f", 1.0, 0.5, 0.25, 1.0)
        archive = _MockArchive(data)
        tag = _make_tag("LinearColor")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "LinearColor"
        assert result.fields["G"] == 0.5


class TestExistingFastPaths:
    """确保原有 fast-path (Vector/Rotator/Vector2D) 不受影响。"""

    def test_vector(self):
        data = struct.pack("<3f", 10, 20, 30)
        archive = _MockArchive(data)
        tag = _make_tag("Vector")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Vector"
        assert result.fields["Z"] == 30

    def test_rotator(self):
        data = struct.pack("<3f", 0, 90, 0)
        archive = _MockArchive(data)
        tag = _make_tag("Rotator")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Rotator"
        assert result.fields["Yaw"] == 90

    def test_vector2d(self):
        data = struct.pack("<2f", 1.5, 2.5)
        archive = _MockArchive(data)
        tag = _make_tag("Vector2D")
        result = parse_struct_property(tag, archive, [], [])
        assert result.struct_type == "Vector2D"
        assert result.fields["Y"] == 2.5
