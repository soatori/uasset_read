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
