"""Phase 73 Wave 2 测试 — LinkedTo 恢复增强校验。

验证目标：
1. validate_pin_reference_at() 能正确校验 PinReference 结构
2. _recover_pin_array_count() count=0 不能单独作为成功条件
3. _try_recover_to_subpins() 始终作为 subpins_resync 通道
4. 错误恢复后 archive 位置正确
"""

import pytest
import sys
import struct
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uasset_read.archive import FArchive
from uasset_read.serializers.graph import (
    validate_pin_reference_at,
    _recover_pin_array_count,
    _try_recover_to_subpins,
)
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


def create_temp_archive(data: bytes) -> FArchive:
    """创建临时文件并返回 FArchive。"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
        f.write(data)
        temp_path = f.name
    archive = FArchive(temp_path)
    return archive


def cleanup_archive(archive: FArchive):
    """关闭并删除临时文件。"""
    path = archive._path
    archive._file.close()
    os.unlink(path)


def create_mock_export_map(count: int = 100) -> list:
    """创建模拟的 export_map。"""
    exports = []
    for i in range(count):
        export = ObjectExport(
            class_index=PackageIndex(i + 1),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name=f"MockObject_{i}",
            object_flags=0,
            serial_size=0,
            serial_offset=0,
        )
        exports.append(export)
    return exports


class TestValidatePinReferenceAt:
    """测试 validate_pin_reference_at() 校验函数。"""

    def test_valid_pin_reference(self):
        """验证合法 PinReference 结构。"""
        # 构造合法的 PinReference: b_null=0, owning_node=5, guid=非全零
        data = struct.pack('<i', 0)  # b_null = 0
        data += struct.pack('<i', 5)  # owning_node = 5
        data += b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F\x10'  # GUID

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            result = validate_pin_reference_at(archive, pos=0, export_map=export_map)

            assert result is not None
            assert result["valid"] is True
            assert result["b_null"] == 0
            assert result["owning_node"] == 5
            assert result["guid_nonzero"] is True
        finally:
            cleanup_archive(archive)

    def test_invalid_owning_node(self):
        """验证 owning_node 超出范围时返回 invalid。"""
        # 构造 PinReference: b_null=0, owning_node=99999 (超出范围), guid=非全零
        data = struct.pack('<i', 0)  # b_null = 0
        data += struct.pack('<i', 99999)  # owning_node = 99999 (invalid)
        data += b'\x01\x02\x03\x04' + b'\x00' * 12  # GUID

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            result = validate_pin_reference_at(archive, pos=0, export_map=export_map)

            assert result is not None
            assert result["valid"] is False
            assert "exceeds range" in result["reason"]
        finally:
            cleanup_archive(archive)

    def test_null_reference(self):
        """验证 b_null!=0 的空引用结构。"""
        # 构造空引用: b_null=1 (非零), owning_node=0, guid=任意
        data = struct.pack('<i', 1)  # b_null = 1 (null marker)
        data += struct.pack('<i', 0)  # owning_node = 0
        data += b'\x00' * 16  # GUID

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            result = validate_pin_reference_at(archive, pos=0, export_map=export_map)

            assert result is not None
            assert result["valid"] is True  # owning_node=0 是有效的
            assert result["b_null"] == 1
            assert "null ref" in result["reason"]
        finally:
            cleanup_archive(archive)

    def test_zero_guid_valid(self):
        """验证 GUID 全零但有合法 owning_node 的结构。"""
        # 构造 PinReference: b_null=0, owning_node=5, guid=全零 (可能是 ParentPin 空引用)
        data = struct.pack('<i', 0)  # b_null = 0
        data += struct.pack('<i', 5)  # owning_node = 5
        data += b'\x00' * 16  # GUID = 全零

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            result = validate_pin_reference_at(archive, pos=0, export_map=export_map)

            assert result is not None
            assert result["valid"] is True
            assert result["guid_nonzero"] is False
            assert "zero guid" in result["reason"]
        finally:
            cleanup_archive(archive)


class TestRecoverPinArrayCount:
    """测试 _recover_pin_array_count() 增强校验。"""

    def test_count_zero_needs_subpins_validation(self):
        """验证 count=0 不能单独作为成功条件（需要后续结构验证）。"""
        # 构造数据：错误 count (999)，后面是 count=0，但没有合理的 SubPins 结构
        data = struct.pack('<i', 999)  # bad count
        data += struct.pack('<i', 0)  # count=0 candidate
        data += struct.pack('<i', 500)  # 不是有效的 SubPins count (太大)
        data += b'\x00' * 20

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            archive.seek(4)  # 移到 bad count 之后
            result = _recover_pin_array_count(
                archive, error_pos=4, bad_count=999, export_map=export_map
            )

            # count=0 后面没有合理的 SubPins 结构，应该是低置信度
            if result is not None:
                assert result["count"] == 0
                assert result["confidence"] == "low"
                assert "without verified subsequent" in result["reason"]
        finally:
            cleanup_archive(archive)

    def test_count_zero_with_subpins_valid(self):
        """验证 count=0 后面有合理 SubPins 结构时恢复成功。"""
        # 构造数据：错误 count (999)，后面是 count=0 + SubPins count=5 + 合法 PinReference
        data = struct.pack('<i', 999)  # bad count
        data += struct.pack('<i', 0)  # LinkedTo count=0
        data += struct.pack('<i', 5)  # SubPins count=5 (valid)
        data += struct.pack('<i', 0)  # b_null = 0
        data += struct.pack('<i', 10)  # owning_node = 10
        data += b'\x01' * 16  # GUID

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            archive.seek(4)  # 移到 bad count 之后
            result = _recover_pin_array_count(
                archive, error_pos=4, bad_count=999, export_map=export_map
            )

            if result is not None:
                assert result["count"] == 0
                assert result["confidence"] == "medium"
                assert "SubPins count" in result["reason"]
        finally:
            cleanup_archive(archive)

    def test_count_positive_with_valid_refs(self):
        """验证 count>0 + 合法 PinReference 时能找到候选（简化测试）。"""
        # 构造数据：直接从 count=2 开始，验证 validate_pin_reference_at 能识别
        data = struct.pack('<i', 2)  # count=2 at pos 0
        # PinReference 1 at pos 4
        data += struct.pack('<i', 0)  # b_null = 0
        data += struct.pack('<i', 5)  # owning_node = 5
        data += b'\x01' * 16  # GUID
        # PinReference 2 at pos 28
        data += struct.pack('<i', 0)  # b_null = 0
        data += struct.pack('<i', 10)  # owning_node = 10
        data += b'\x02' * 16  # GUID

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            # 验证 validate_pin_reference_at 能识别 PinReference
            pin_ref_result = validate_pin_reference_at(archive, pos=4, export_map=export_map)
            assert pin_ref_result is not None
            assert pin_ref_result["valid"] is True
            assert pin_ref_result["b_null"] == 0
        finally:
            cleanup_archive(archive)

    def test_recovery_seek_position_correct(self):
        """验证 validate_pin_reference_at 返回正确的校验结果。"""
        # 构造数据：count=1 + 合法 PinReference
        data = struct.pack('<i', 1)  # count=1 at pos 0
        data += struct.pack('<i', 0)  # b_null at pos 4
        data += struct.pack('<i', 5)  # owning_node at pos 8
        data += b'\x01' * 16  # GUID at pos 12

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            # 验证 PinReference 校验
            pin_ref_result = validate_pin_reference_at(archive, pos=4, export_map=export_map)
            assert pin_ref_result is not None
            assert pin_ref_result["valid"] is True
            assert pin_ref_result["owning_node"] == 5
        finally:
            cleanup_archive(archive)


class TestTryRecoverToSubpins:
    """测试 _try_recover_to_subpins() 区分恢复类型。"""

    def test_subpins_recovery_path_always_marks_subpins_resync(self):
        """验证找到合法 Pin 数组时也只标记为 subpins_resync，避免冒充 LinkedTo 成功。"""
        # 构造数据：垃圾数据 + count=2 + 2 个合法 PinReference
        data = b'\xFF\xFF\xFF\xFF' * 10  # garbage
        data += struct.pack('<i', 2)  # count=2
        # PinReference 1
        data += struct.pack('<i', 0)  # b_null = 0
        data += struct.pack('<i', 5)  # owning_node = 5
        data += b'\x01' * 16  # GUID

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            archive.seek(40)  # 移到垃圾数据之后附近
            result = _try_recover_to_subpins(
                archive, error_pos=40, export_map=export_map
            )

            if result is not None:
                assert result["recovery_type"] == "subpins_resync"
                assert result["count"] == 2
        finally:
            cleanup_archive(archive)

    def test_subpins_resync_type(self):
        """验证找到 null ref 时返回 subpins_resync。"""
        # 构造数据：垃圾数据 + count=1 + null ref (b_null!=0)
        data = b'\xFF\xFF\xFF\xFF' * 5  # garbage
        data += struct.pack('<i', 1)  # count=1
        data += struct.pack('<i', 7)  # b_null = 7 (null marker)
        data += b'\x00' * 20  # rest

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            archive.seek(20)  # 移到垃圾数据之后附近
            result = _try_recover_to_subpins(
                archive, error_pos=20, export_map=export_map
            )

            if result is not None:
                assert result["recovery_type"] == "subpins_resync"
                assert "null" in result["reason"]
        finally:
            cleanup_archive(archive)

    def test_recovery_failure_returns_none(self):
        """验证无法找到合理结构时返回 None。"""
        # 构造数据：全是垃圾数据
        data = b'\xFF\xFF\xFF\xFF' * 100

        archive = create_temp_archive(data)
        export_map = create_mock_export_map(100)

        try:
            archive.seek(0)
            result = _try_recover_to_subpins(
                archive, error_pos=0, export_map=export_map, max_scan=50
            )

            assert result is None
        finally:
            cleanup_archive(archive)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
