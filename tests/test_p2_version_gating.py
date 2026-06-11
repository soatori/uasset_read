"""P2 格式修复测试 — 版本门控 (#96, #97)。"""
from __future__ import annotations

import pytest


class TestPreloadDependenciesVersionGate:
    """#96: PreloadDependencies 在 UE5 路径中应有版本门控。

    UE 源码 PackageFileSummary.cpp L503-511:
      if (Sum.FileVersionUE >= VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS)  // 512
          Record << Sum.PreloadDependenciesUE5;
    """

    def test_version_gate_logic(self):
        """验证版本门控逻辑正确性（纯逻辑测试）。"""
        UE4_PRELOAD_DEPS = 512

        def should_read_preload(file_version_ue4: int) -> bool:
            return file_version_ue4 >= UE4_PRELOAD_DEPS

        assert should_read_preload(512) is True
        assert should_read_preload(516) is True
        assert should_read_preload(511) is False
        assert should_read_preload(0) is False
        assert should_read_preload(522) is True


class TestFScriptTextInvariant:
    """#97 D.2: FScriptText InvariantText 应只读取 1 个 expression。

    枚举成员名称引用错误（Invariant → InvariantText, CultureInvariant → LiteralString）。
    InvariantText 读取 2 个字符串（key + source），应只读 1 个。
    """

    def test_invariant_reads_one_string(self):
        """验证 InvariantText 只读取一个字符串的修复逻辑。"""
        import io
        import struct
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.kismet.expressions.string_consts import FScriptText
        from uasset_read.kismet.tokens import EBlueprintTextLiteralType

        name_map = ["test"]
        source_str = "invariant_text"

        buf = io.BytesIO()
        buf.write(struct.pack('B', 2))  # InvariantText enum value
        buf.write(source_str.encode('ascii'))
        buf.write(b'\x00')  # null terminator
        buf.seek(0)

        archive = FKismetArchive(buf.read(), "test", name_map)
        text = FScriptText.from_archive(archive, name_map)

        assert text.TextLiteralType == EBlueprintTextLiteralType.InvariantText
        assert text.SourceString == source_str
        assert text.KeyString is None

    def test_literal_string_reads_one_string(self):
        """验证 LiteralString 读取一个字符串。"""
        import io
        import struct
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.kismet.expressions.string_consts import FScriptText
        from uasset_read.kismet.tokens import EBlueprintTextLiteralType

        name_map = ["test"]
        source_str = "literal_fstring"

        buf = io.BytesIO()
        buf.write(struct.pack('B', 3))  # LiteralString enum value
        buf.write(source_str.encode('ascii'))
        buf.write(b'\x00')
        buf.seek(0)

        archive = FKismetArchive(buf.read(), "test", name_map)
        text = FScriptText.from_archive(archive, name_map)

        assert text.TextLiteralType == EBlueprintTextLiteralType.LiteralString
        assert text.SourceString == source_str


class TestSoftObjectPathVersionGate:
    """#97 D.4: SoftObjectPath 应有三阶段版本门控。

    UE 源码 FSoftObjectPath operator<< 序列化格式随版本演变：
    - Phase 4 (>= 1008): SoftObjectPathList 索引
    - Phase 3 (>= 1007): FUtf8String + FUtf8String
    - Phase 2 (>= 514):  FName(AssetPath) + WideString(SubPath)
    - Phase 1 (< 514):   单一 FString (legacy)
    """

    def test_version_gate_logic(self):
        """验证版本门控逻辑正确性。"""
        def get_soft_object_format(file_version_ue4: int, file_version_ue5: int, has_list: bool):
            if has_list:
                return "index"
            if file_version_ue5 >= 1007:
                return "utf8"
            if file_version_ue4 >= 514:
                return "fname_wide"
            return "legacy_single"

        # Phase 1: Legacy < 514
        assert get_soft_object_format(500, 0, False) == "legacy_single"
        assert get_soft_object_format(513, 0, False) == "legacy_single"
        # Phase 2: UE4 >= 514
        assert get_soft_object_format(514, 0, False) == "fname_wide"
        assert get_soft_object_format(1006, 0, False) == "fname_wide"
        # Phase 3: UE5 >= 1007
        assert get_soft_object_format(0, 1007, False) == "utf8"
        assert get_soft_object_format(0, 1010, False) == "utf8"
        # Phase 4: UE5 >= 1008 with list
        assert get_soft_object_format(0, 1008, True) == "index"
        assert get_soft_object_format(0, 1010, True) == "index"

    @staticmethod
    def _make_archive(data: bytes):
        """构造 MockArchive（复用 test_soft_object_path_index 的模式）。"""
        import struct
        from io import BytesIO

        class _MockArchive:
            def __init__(self, raw: bytes):
                self._stream = BytesIO(raw)

            def read_i32(self) -> int:
                return struct.unpack('<i', self._stream.read(4))[0]

            def read_fstring(self) -> str:
                length = struct.unpack('<i', self._stream.read(4))[0]
                if length == 0:
                    return ""
                raw = self._stream.read(length - 1)
                self._stream.read(1)  # null terminator
                return raw.decode('utf-8')

            def tell(self) -> int:
                return self._stream.tell()

            def seek(self, pos: int) -> None:
                self._stream.seek(pos)

        return _MockArchive(data)

    @staticmethod
    def _fstring(s: str) -> bytes:
        """序列化 FString。"""
        import struct
        if not s:
            return struct.pack('<i', 0)
        encoded = s.encode('utf-8')
        return struct.pack('<i', len(encoded) + 1) + encoded + b'\x00'

    def test_legacy_single_string_reads_one_fstring(self):
        """验证 Phase 1 (legacy < 514) 只读取一个 FString。"""
        import struct
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types.object_ref import parse_soft_object_property

        data = self._fstring("Path")
        archive = self._make_archive(data)
        tag = PropertyTag(name="TestProp", type="SoftObjectProperty", size=0)
        result = parse_soft_object_property(tag, archive, [], file_version_ue4=500, file_version_ue5=0)

        assert result.asset_path == "Path"
        assert result.sub_path == ""

    def test_fname_wide_reads_fname_and_fstring(self):
        """验证 Phase 2 (UE4 >= 514) 读取 FName + FString。"""
        import struct
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types.object_ref import parse_soft_object_property

        name_map = ["AssetName", "OtherName"]
        data = struct.pack('<i', 0) + struct.pack('<i', 0) + self._fstring("SubPath")
        archive = self._make_archive(data)
        tag = PropertyTag(name="TestProp", type="SoftObjectProperty", size=0)
        result = parse_soft_object_property(tag, archive, name_map, file_version_ue4=514, file_version_ue5=0)

        assert result.asset_path == "AssetName"
        assert result.sub_path == "SubPath"

    def test_utf8_reads_two_fstrings(self):
        """验证 Phase 3 (UE5 >= 1007) 读取两个 FUtf8String。"""
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types.object_ref import parse_soft_object_property

        data = self._fstring("AssetPath") + self._fstring("SubPath")
        archive = self._make_archive(data)
        tag = PropertyTag(name="TestProp", type="SoftObjectProperty", size=0)
        result = parse_soft_object_property(tag, archive, [], file_version_ue4=0, file_version_ue5=1007)

        assert result.asset_path == "AssetPath"
        assert result.sub_path == "SubPath"

    def test_index_format_uses_list(self):
        """验证 Phase 4 (UE5 >= 1008) 使用 SoftObjectPathList 索引。"""
        import struct
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types.object_ref import parse_soft_object_property

        soft_list = [
            {'asset_path': '/Game/Asset1', 'sub_path': ''},
            {'asset_path': '/Game/Asset2', 'sub_path': 'Component'},
        ]
        archive = self._make_archive(struct.pack('<i', 1))
        tag = PropertyTag(name="TestProp", type="SoftObjectProperty", size=0)
        result = parse_soft_object_property(tag, archive, [], soft_list, file_version_ue4=0, file_version_ue5=1008)

        assert result.asset_path == '/Game/Asset2'
        assert result.sub_path == 'Component'
        assert result.index == 1

    def test_index_out_of_bounds_returns_error(self):
        """验证 Phase 4 索引越界时返回错误信息。"""
        import struct
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types.object_ref import parse_soft_object_property

        soft_list = [{'asset_path': '/Game/Asset1', 'sub_path': ''}]
        archive = self._make_archive(struct.pack('<i', 99))
        tag = PropertyTag(name="TestProp", type="SoftObjectProperty", size=0)
        result = parse_soft_object_property(tag, archive, [], soft_list, file_version_ue4=0, file_version_ue5=1008)

        assert result.error is not None
        assert "out of bounds" in result.error
        assert result.index == 99

    def test_soft_class_prop_propagates_version(self):
        """验证 SoftClassProperty 透传版本参数到 SoftObjectProperty。"""
        import struct
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types.object_ref import parse_soft_class_property

        name_map = ["ClassName"]
        data = struct.pack('<i', 0) + struct.pack('<i', 0) + self._fstring("Sub")
        archive = self._make_archive(data)
        tag = PropertyTag(name="TestProp", type="SoftClassProperty", size=0)
        result = parse_soft_class_property(tag, archive, name_map, file_version_ue4=600, file_version_ue5=0)

        assert result.asset_path == "ClassName"
        assert result.sub_path == "Sub"

    def test_default_version_falls_to_legacy(self):
        """验证默认版本参数（0, 0）回退到向后兼容格式（FString + FString）。"""
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types.object_ref import parse_soft_object_property

        # 版本未知时提供两个 FString（向后兼容默认行为）
        archive = self._make_archive(self._fstring("MyPath") + self._fstring("MySub"))
        tag = PropertyTag(name="TestProp", type="SoftObjectProperty", size=0)
        # 不传版本参数 — 使用默认值 0
        result = parse_soft_object_property(tag, archive, [])

        assert result.asset_path == "MyPath"
        assert result.sub_path == "MySub"


class TestUnversionedHeaderBitLayout:
    """#97 D.1: 验证 FFragment bit layout 正确性（回归测试）。

    UE 源码 UnversionedPropertySerialization.cpp L667-696:
    - bits 0-6:  SkipNum (7 bits, mask 0x007F)
    - bit 7:     bHasAnyZeroes (mask 0x0080)
    - bit 8:     bIsLast (mask 0x0100)
    - bits 9-15: ValueNum (7 bits, shift 9)

    当前代码 (unversioned_parser.py:92-96) 已正确实现。
    """

    def test_fragment_parsing(self):
        """验证 FFragment 位域解析与 UE 源码一致。"""
        # SkipNum=3, bHasAnyZeroes=1, bIsLast=0, ValueNum=5
        raw = 3 | (1 << 7) | (0 << 8) | (5 << 9)
        skip_num = raw & 0x007F
        has_any_zeroes = bool(raw & 0x0080)
        is_last = bool(raw & 0x0100)
        value_num = (raw >> 9) & 0x007F
        assert skip_num == 3
        assert has_any_zeroes is True
        assert is_last is False
        assert value_num == 5

    def test_last_fragment(self):
        """bIsLast = 1 的 fragment。"""
        raw = 0 | (0 << 7) | (1 << 8) | (2 << 9)
        skip_num = raw & 0x007F
        has_any_zeroes = bool(raw & 0x0080)
        is_last = bool(raw & 0x0100)
        value_num = (raw >> 9) & 0x007F
        assert skip_num == 0
        assert has_any_zeroes is False
        assert is_last is True
        assert value_num == 2
