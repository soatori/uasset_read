"""Phase 72g M-01: Vector/Rotator 快速路径解析回归测试。"""
import struct
import tempfile
import os

import pytest

from uasset_read.archive import FArchive
from uasset_read.models.properties import PropertyTag
from uasset_read.parsers.property_types import parse_struct_property, StructValue


SAMPLE_ASSET = "E:\\Develop\\lib\\UnrealEngine\\Samples\\FirstPerson\\BP_FirstPersonCharacter.uasset"


def _make_archive(data: bytes) -> FArchive:
    """Create a temporary file and return FArchive pointing to it."""
    fd, path = tempfile.mkstemp(suffix='.bin')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
    except:
        os.close(fd)
        raise
    return FArchive(path, tolerant=True), path


def _cleanup(archive: FArchive, path: str):
    try:
        archive.close()
    except Exception:
        pass
    try:
        os.unlink(path)
    except Exception:
        pass


class TestVectorFastPath:
    """测试 Vector 直接 float 读取快速路径。"""

    def test_vector_fast_path(self):
        """mock archive with 3 floats, verify StructValue fields."""
        data = struct.pack('<fff', 100.0, 200.0, 300.0)
        archive, path = _make_archive(data)
        try:
            tag = PropertyTag(name="RelativeLocation", type="StructProperty(Vector)", size=12)
            result = parse_struct_property(tag, archive, name_map=[], export_map=[])
            assert isinstance(result, StructValue)
            assert result.struct_type == "Vector"
            assert result.fields["X"] == pytest.approx(100.0)
            assert result.fields["Y"] == pytest.approx(200.0)
            assert result.fields["Z"] == pytest.approx(300.0)
        finally:
            _cleanup(archive, path)

    def test_rotator_fast_path(self):
        """mock archive with 3 floats, verify StructValue fields."""
        data = struct.pack('<fff', 45.0, 90.0, 0.0)
        archive, path = _make_archive(data)
        try:
            tag = PropertyTag(name="RelativeRotation", type="StructProperty(Rotator)", size=12)
            result = parse_struct_property(tag, archive, name_map=[], export_map=[])
            assert isinstance(result, StructValue)
            assert result.struct_type == "Rotator"
            assert result.fields["Pitch"] == pytest.approx(45.0)
            assert result.fields["Yaw"] == pytest.approx(90.0)
            assert result.fields["Roll"] == pytest.approx(0.0)
        finally:
            _cleanup(archive, path)

    def test_vector2d_fast_path(self):
        """mock archive with 2 floats, verify StructValue fields."""
        data = struct.pack('<ff', 50.0, 75.0)
        archive, path = _make_archive(data)
        try:
            tag = PropertyTag(name="Offset2D", type="StructProperty(Vector2D)", size=8)
            result = parse_struct_property(tag, archive, name_map=[], export_map=[])
            assert isinstance(result, StructValue)
            assert result.struct_type == "Vector2D"
            assert result.fields["X"] == pytest.approx(50.0)
            assert result.fields["Y"] == pytest.approx(75.0)
        finally:
            _cleanup(archive, path)

    def test_other_struct_uses_property_tags_loop(self):
        """Non-fast-path struct still uses PropertyTags loop and returns StructValue."""
        # Provide a "None" terminator: read_name reads 2x u32 (index + number),
        # if index out of range of name_map it returns "None"
        data = struct.pack('<II', 0xFFFFFFFF, 0)  # index=0xFFFFFFFF (out of range) → "None"
        archive, path = _make_archive(data)
        try:
            tag = PropertyTag(name="Color", type="StructProperty(LinearColor)", size=0)
            result = parse_struct_property(tag, archive, name_map=[], export_map=[])
            assert isinstance(result, StructValue)
            assert result.struct_type == "LinearColor"
        finally:
            _cleanup(archive, path)
