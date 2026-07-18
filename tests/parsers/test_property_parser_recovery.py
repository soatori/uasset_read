"""PropertyTag 偏移恢复机制测试。

合并来源：
- test_array_property_bounds.py
- test_property_types_warnings.py
- test_top_level_asset_path.py
"""
import logging

import pytest
from unittest.mock import MagicMock

from uasset_read.parsers.property_parser import _try_recover_property_tag
from uasset_read.parsers.property_types import (
    _EXPECTED_STRUCT_SIZES,
    _TAGGED_FALLBACK_STRUCTS,
    parse_array_property,
    parse_struct_property,
)
from uasset_read.models.properties import PropertyTag
from uasset_read.constants import PROPERTY_TAG_COMPLETE_TYPE_NAME


# legacy 版本号（UE5 < 1012），使用简单 FName 类型格式
_LEGACY_UE5 = 0


class TestPropertyTagRecovery:
    """#341: PropertyTag 早期损坏恢复测试。"""

    def _make_archive(self, data: bytes, pos: int = 0, *, file_version_ue5: int = PROPERTY_TAG_COMPLETE_TYPE_NAME):
        """创建 mock FArchive。

        Args:
            data: 原始字节数据
            pos: 初始读取位置
            file_version_ue5: UE5 版本号，默认 UE5.3+ (1012)
        """
        archive = MagicMock()
        archive._data = data
        archive._pos = pos
        archive._file_size = len(data)
        archive._file_version_ue5 = file_version_ue5

        def tell():
            return archive._pos

        def seek(p):
            archive._pos = p

        def read(n):
            start = archive._pos
            archive._pos += n
            return data[start:start + n]

        archive.tell = tell
        archive.seek = seek
        archive.read = read
        return archive

    def test_recovery_finds_valid_tag_signature_legacy(self):
        """legacy 格式：恢复函数能找到有效的 PropertyTag（name + type_fname + size）。"""
        import struct
        name_map = ["None", "Property", "TestProp"]
        # legacy: name(8) + type_fname(8) + size(4) = 20 bytes from candidate
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)        # "TestProp"
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)   # "Property"
        size = struct.pack('<i', 10)
        data = b'\x00\x00\x00' + fname + type_fname + size + b'\xff' * 30
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_finds_valid_tag_signature_ue53(self):
        """UE5.3+ 格式：恢复函数能找到有效的 PropertyTag（name + type_tree + size）。"""
        import struct
        name_map = ["None", "Property", "TestProp"]
        # UE5.3+: name(8) + type_tree(FName(8) + inner_count(4)) + size(4) = 24 bytes
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)        # "TestProp"
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)   # "Property" (type tree node)
        inner_count = struct.pack('<i', 0)                         # 无子节点
        size = struct.pack('<i', 10)
        data = b'\x00\x00\x00' + fname + type_fname + inner_count + size + b'\xff' * 30
        archive = self._make_archive(data, pos=0)

        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_returns_false_when_no_valid_tag(self):
        """无有效签名时返回 False。"""
        data = b'\xff' * 100
        archive = self._make_archive(data, pos=0)

        result = _try_recover_property_tag(archive, ["None"], max_scan=32)
        assert result is False

    def test_recovery_respects_property_boundary(self):
        """恢复不会越过属性数据边界，但能找到边界内的有效签名。"""
        import struct
        name_map = ["None", "Property", "TestProp", "GoodProp"]
        # legacy 格式：偏移 5 处放完整 PropertyTag
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 10)
        data = b'\xff' * 5 + fname + type_fname + size + b'\xff' * 20
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        # property_end 使偏移 5 的 size 可验证（size_pos=21, size_remaining=35-25=10）
        result = _try_recover_property_tag(archive, name_map, max_scan=50, property_end=35)
        assert result is True
        assert archive.tell() == 5

    def test_recovery_with_real_fname_format(self):
        """恢复函数能识别真实的 FName 二进制格式（uint32 index + uint32 number）。"""
        import struct
        name_map = ["None", "Property", "TestProp", "TaggedProperty"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 10)
        data = b'\x00\x00\x00' + fname + type_fname + size + b'\xff' * 30
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_rejects_ascii_payload_as_fname(self):
        """属性 payload 中的普通 ASCII 数据不会被误判为 FName 边界。"""
        import struct
        name_map = ["None", "Property"]
        ascii_payload = b'Hello World!'  # 12 bytes - 旧扫描器会误命中
        real_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 5)
        data = b'\xff\xfe' + ascii_payload + real_fname + type_fname + size + b'\xff' * 10
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 14

    def test_recovery_validates_index_against_name_map(self):
        """恢复函数通过 name_map 验证候选索引的有效性。"""
        import struct
        name_map = ["None", "Property", "TestProp"]
        bad_fname = struct.pack('<I', 999) + struct.pack('<I', 0)
        good_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 5)
        data = b'\xff\x00' + bad_fname + b'\xff\x00' + good_fname + type_fname + size + b'\xff' * 10
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 12

    def test_recovery_validates_tag_size_after_fname(self):
        """恢复函数在找到候选 FName 后检查后续 PropertyTag size 字段。"""
        import struct
        name_map = ["None", "Property", "TestProp"]
        # legacy: name(8) + type(8) + size(4) = 20 bytes from candidate
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 48)
        data = b'\x00\x00\x00' + fname + type_fname + size + b'\x00' * 50
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=200)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_rejects_candidate_when_size_exceeds_boundary(self):
        """当 PropertyTag size 超出属性边界时，候选位置被拒绝。"""
        import struct
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        huge_size = struct.pack('<i', 500)
        data = b'\x00\x00\x00' + fname + type_fname + huge_size + b'\xff' * 20
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=50)
        assert result is False

    def test_recovery_rejects_negative_tag_size(self):
        """当 PropertyTag size 为负数时，候选位置被拒绝。"""
        import struct
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        neg_size = struct.pack('<i', -1)
        data = b'\x00\x00\x00' + fname + type_fname + neg_size + b'\xff' * 20
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=200)
        assert result is False

    def test_recovery_rejects_window_end_candidate(self):
        """窗口末端无法验证 size 的候选被拒绝（宁可漏报不误报）。"""
        import struct
        name_map = ["None", "Property", "TestProp"]
        # 偏移 55 处放 FName，size 字段超出 64 字节窗口
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        data = b'\xff' * 55 + fname + b'\xff' * 40
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is False

    def test_recovery_ue53_rejects_inner_count_as_size(self):
        """UE5.3+ 格式：inner_count=0 不应被误判为 size=0。

        回归测试：旧实现用固定偏移 +16 读 UE5.3+ 布局，把 inner_count=0
        当作合法 size=0，接受实际 size 越界的候选。
        """
        import struct
        name_map = ["None", "IntProperty", "TestProp"]

        # UE5.3+ 布局：name(8) + type_tree(FName(8) + inner_count(4)) + size(4)
        # 实际 size=500 越过属性边界
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)             # "TestProp"
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)        # "IntProperty"
        inner_count = struct.pack('<i', 0)                              # 无子节点
        actual_size = struct.pack('<i', 500)                            # 越界 size
        data = b'\xff' * 3 + fname + type_fname + inner_count + actual_size + b'\xff' * 20
        archive = self._make_archive(data, pos=0)

        # property_end=30, size_pos=27, size_remaining=30-31=-1 → 500 > -1 → 拒绝
        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=30)
        assert result is False

    def test_recovery_ue53_with_multi_node_type_tree(self):
        """UE5.3+ 多节点类型树：正确跳过整个树后验证 size。"""
        import struct
        name_map = ["None", "StructProperty", "Vector", "TestProp"]

        # UE5.3+ 布局：name(8) + type_tree(3节点) + size(4)
        # type_tree: StructProperty(children=1) → Vector(children=0) → (内部子节点)
        fname = struct.pack('<I', 3) + struct.pack('<I', 0)             # "TestProp"
        # 节点 1: StructProperty, inner_count=1（有1个子节点）
        node1 = struct.pack('<I', 1) + struct.pack('<I', 0) + struct.pack('<i', 1)
        # 节点 2: Vector, inner_count=0（叶子）
        node2 = struct.pack('<I', 2) + struct.pack('<I', 0) + struct.pack('<i', 0)
        size = struct.pack('<i', 20)
        data = b'\xff' * 3 + fname + node1 + node2 + size + b'\xff' * 30
        archive = self._make_archive(data, pos=0)

        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=200)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_legacy_rejects_ue53_inner_count_as_type_index(self):
        """legacy 版本不应把 UE5.3+ 的 inner_count=0 当作合法 type index。

        当 archive 版本为 legacy 时，+8 位置必须是有效的 type FName index。
        如果该位置是 inner_count=0（恰好等于 "None" 的 index），应被
        type_name != "None" 过滤掉。
        """
        import struct
        name_map = ["None", "Property", "TestProp"]

        # 构造 UE5.3+ 布局，但用 legacy 版本解析
        # name(8) + type_tree_fname(8) + inner_count(4) + actual_size(4)
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)         # "TestProp"
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)    # "Property"
        inner_count = struct.pack('<i', 0)                          # +16 位置
        data = b'\xff' * 3 + fname + type_fname + inner_count + b'\xff' * 20
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        # legacy 解析：+8 处 type_fname index=1 有效，+16 处 size=inner_count=0 → 有效
        # 这是正常的 legacy 解析，inner_count 位置恰好是 size 位置，0 是合法 size
        # 此测试验证 legacy 路径确实把 +16 当作 size（而非拒绝）
        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=200)
        assert result is True  # legacy 模式下，+16 读到 size=0 是合法的

    def test_recovery_finds_valid_position(self):
        """恢复到有效 FName 位置应成功。"""
        import struct
        name_map = ["None", "IntProperty", "TestProp"]
        # 有效 FName 距离当前位置 10 字节
        valid_fname = struct.pack('<I', 2) + struct.pack('<I', 0)    # "TestProp"
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)   # "IntProperty"
        size = struct.pack('<i', 8)
        data = b'\xff' * 10 + valid_fname + type_fname + size + b'\xff' * 30
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 10

    def test_recovery_stops_at_max_scan(self):
        """扫描不应超过最大字节限制。"""
        import struct
        name_map = ["None", "IntProperty", "TestProp"]
        # 有效 FName 在 offset 100，但 max_scan=50，应找不到
        valid_fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 8)
        data = b'\xff' * 100 + valid_fname + type_fname + size + b'\xff' * 30
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        result = _try_recover_property_tag(archive, name_map, max_scan=50)
        assert result is False
        # 位置应恢复到原始位置
        assert archive.tell() == 0

    def test_recovery_records_distance(self):
        """恢复操作应记录扫描距离（通过返回后的 tell 位置计算）。"""
        import struct
        name_map = ["None", "IntProperty", "TestProp"]
        # 有效 FName 在 offset 20
        valid_fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 8)
        data = b'\xff' * 20 + valid_fname + type_fname + size + b'\xff' * 30
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        start = archive.tell()
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        distance = archive.tell() - start
        assert distance == 20

    def test_fallback_when_no_valid_position(self):
        """无有效位置时应回退到最小跳过（返回 False，位置不变）。"""
        data = b'\xff' * 100
        archive = self._make_archive(data, pos=0)

        result = _try_recover_property_tag(archive, ["None"], max_scan=50)
        assert result is False
        # 位置应恢复到原始位置（调用者负责 1 字节跳过）
        assert archive.tell() == 0

    def test_max_recovery_scan_constant_value(self):
        """_MAX_RECOVERY_SCAN 常量应为 256。"""
        from uasset_read.parsers.property_parser import _MAX_RECOVERY_SCAN
        assert _MAX_RECOVERY_SCAN == 256

    def test_recovery_uses_max_recovery_scan_default(self):
        """调用方应使用 _MAX_RECOVERY_SCAN 作为默认扫描范围。"""
        from uasset_read.parsers.property_parser import _MAX_RECOVERY_SCAN
        import struct
        name_map = ["None", "IntProperty", "TestProp"]
        # 有效 FName 在 offset 200（超过旧默认 64，但在新默认 256 内）
        valid_fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 8)
        data = b'\xff' * 200 + valid_fname + type_fname + size + b'\xff' * 30
        archive = self._make_archive(data, pos=0, file_version_ue5=_LEGACY_UE5)

        # 使用 _MAX_RECOVERY_SCAN 应能找到偏移 200 处的签名
        result = _try_recover_property_tag(archive, name_map, max_scan=_MAX_RECOVERY_SCAN)
        assert result is True
        assert archive.tell() == 200


# ============================================================================
# ArrayProperty tag.size < 4 测试（合并自 test_array_property_bounds.py）
# ============================================================================


class TrackingArchive:
    """记录 read_i32 调用次数。"""
    def __init__(self):
        self.pos = 0
        self.read_count = 0
    def tell(self):
        return self.pos
    def read_i32(self):
        self.read_count += 1
        self.pos += 4
        return 0
    def read_fstring(self):
        return ""
    def read_byte(self):
        return 0


def test_small_tag_size_skips_count_read():
    """tag.size < 4 不应读取 count。"""
    for size in (0, 1, 3):
        a = TrackingArchive()
        tag = PropertyTag(name="A", type="ArrayProperty", size=size)
        result = parse_array_property(tag, a, [], [])
        assert result == [], f"size={size}: 应返回空数组"
        assert a.read_count == 0, f"size={size}: 不应调用 read_i32 (count)"


# ============================================================================
# 属性类型日志级别测试（合并自 test_property_types_warnings.py）
# ============================================================================


class TestTransformWarningDowngrade:
    """#340: Transform size 警告应降级为 debug。"""

    def test_unknown_transform_variant_logs_debug_not_warning(self):
        """未知 Transform 变体应使用 debug 级别（不触发 warning）。"""
        # 创建 mock tag 和 archive
        tag = MagicMock()
        tag.name = "TestTransform"
        tag.type = "StructProperty"
        tag.struct_type = "Transform"
        tag.size = 48  # 非标准 size (float=40, double=80)
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 48)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)
        archive._tolerant = True

        name_map = []
        export_map = []

        # 直接设置 logger 级别确保 debug 消息被捕获
        test_logger = logging.getLogger("uasset_read.parsers.property_types")
        old_level = test_logger.level
        test_logger.setLevel(logging.DEBUG)
        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)
        test_logger.addHandler(handler)
        try:
            try:
                parse_struct_property(tag, archive, name_map, export_map)
            except Exception:
                pass  # mock 不完整，关注日志级别
        finally:
            test_logger.removeHandler(handler)
            test_logger.setLevel(old_level)

        # 应该有 debug 日志（标记 size 不匹配），无 warning
        debug_msgs = [r for r in captured if r.levelno == logging.DEBUG]
        warning_msgs = [r for r in captured if r.levelno == logging.WARNING
                        and 'Transform' in r.message]
        assert len(debug_msgs) > 0, f"Expected debug logs but got none"
        assert len(warning_msgs) == 0, f"Expected no warnings but got: {warning_msgs}"

    def test_unknown_non_lwc_struct_variant_logs_debug_not_warning(self):
        """非 LWC 结构体的未知变体也应使用 debug 级别。"""
        tag = MagicMock()
        tag.name = "TestStruct"
        tag.type = "StructProperty"
        tag.struct_type = "Vector"  # 在 _EXPECTED_STRUCT_SIZES 中（非 LWC 变体），但 size 不匹配
        tag.size = 99  # 不匹配预期的 12，触发非 LWC 分支（line 749）
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 99)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)

        name_map = []
        export_map = []

        # 直接设置 logger 级别确保 debug 消息被捕获
        test_logger = logging.getLogger("uasset_read.parsers.property_types")
        old_level = test_logger.level
        test_logger.setLevel(logging.DEBUG)
        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)
        test_logger.addHandler(handler)
        try:
            try:
                parse_struct_property(tag, archive, name_map, export_map)
            except Exception:
                pass  # mock 不完整，关注日志级别
        finally:
            test_logger.removeHandler(handler)
            test_logger.setLevel(old_level)

        # 应该有 debug 日志，没有 warning
        debug_msgs = [r for r in captured if r.levelno == logging.DEBUG]
        warning_msgs = [r for r in captured if r.levelno == logging.WARNING
                        and 'Vector' in r.message]
        assert len(debug_msgs) > 0 and len(warning_msgs) == 0

    def test_standard_transform_size_no_warning(self, caplog):
        """标准 Transform size (40 或 80) 不应产生任何日志。"""
        tag = MagicMock()
        tag.name = "TestTransform"
        tag.type = "StructProperty"
        tag.struct_type = "Transform"
        tag.size = 40  # 标准 float 尺寸
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 40)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)

        name_map = []
        export_map = []

        with caplog.at_level(logging.DEBUG):
            try:
                parse_struct_property(tag, archive, name_map, export_map)
            except Exception:
                pass

        # 标准尺寸不应有 size mismatch 相关日志
        size_mismatch_msgs = [r for r in caplog.records
                              if 'tag.size' in r.message and 'Transform' in r.message]
        assert len(size_mismatch_msgs) == 0


class TestArrayPropertySmallSize:
    """#345: ArrayProperty tag.size < 4 处理测试。"""

    def test_empty_array_no_warning(self, caplog):
        """tag.size=0 表示空数组，不应输出 warning。"""
        tag = MagicMock()
        tag.name = "DebugWatch_RigVMModel___Test"
        tag.type = "ArrayProperty"
        tag.size = 0  # 空数组
        tag.array_index = 0
        tag.inner_type = "IntProperty"

        archive = MagicMock()
        archive.read_i32 = MagicMock(return_value=0)  # count = 0
        archive.tell = MagicMock(return_value=0)

        with caplog.at_level(logging.WARNING):
            result = parse_array_property(tag, archive, [], [])

        assert result == []
        # 不应有 warning 关于 tag.size < 4
        size_warnings = [r for r in caplog.records
                        if r.levelno >= logging.WARNING and 'tag.size' in r.message]
        assert len(size_warnings) == 0

    def test_tag_size_1_no_warning(self, caplog):
        """tag.size=1 也应静默处理（RigVM DebugWatch 场景）。"""
        tag = MagicMock()
        tag.name = "DebugWatch_RigVMModel___Test[0]"
        tag.type = "ArrayProperty"
        tag.size = 1
        tag.array_index = 0
        tag.inner_type = "IntProperty"

        archive = MagicMock()
        archive.read_i32 = MagicMock(return_value=0)
        archive.tell = MagicMock(return_value=0)

        with caplog.at_level(logging.WARNING):
            result = parse_array_property(tag, archive, [], [])

        assert result == []
        size_warnings = [r for r in caplog.records
                        if r.levelno >= logging.WARNING and 'tag.size' in r.message]
        assert len(size_warnings) == 0


# ============================================================================
# TopLevelAssetPath 结构体测试（合并自 test_top_level_asset_path.py）
# ============================================================================


class TestTopLevelAssetPath:
    def test_expected_size_is_none(self):
        """TopLevelAssetPath 应为 None（可变大小，由 fast-path 直接处理）。"""
        size = _EXPECTED_STRUCT_SIZES.get("TopLevelAssetPath")
        assert size is None

    def test_not_in_tagged_fallback_structs(self):
        """TopLevelAssetPath 不应在 _TAGGED_FALLBACK_STRUCTS 中（expected_size=None 时 size-mismatch 块被跳过）。"""
        assert "TopLevelAssetPath" not in _TAGGED_FALLBACK_STRUCTS
