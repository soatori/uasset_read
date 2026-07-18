"""archive.py 内联 import 和 serialize_bits 修复测试 (#246)。

TDD: 先写失败测试，再实现修复。
"""
import ast
import sys
import pytest
from pathlib import Path

ARCHIVE_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "uasset_read" / "archive.py"


# ---------------------------------------------------------------------------
# 测试 1: 模块级没有 import struct / import math / __import__('os')
# ---------------------------------------------------------------------------

class TestNoInlineImports:
    """验证 archive.py 不包含函数体内的内联 import。"""

    @pytest.fixture(autouse=True)
    def _parse_archive(self):
        self._source = ARCHIVE_PATH.read_text(encoding="utf-8")
        self._tree = ast.parse(self._source)

    def _function_body_imports(self, module: ast.Module) -> list[tuple[str, int]]:
        """收集所有函数/方法体内的 import 语句。"""
        results = []
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Import):
                        for alias in child.names:
                            results.append((alias.name, child.lineno))
                    elif isinstance(child, ast.ImportFrom):
                        if child.module:
                            results.append((child.module, child.lineno))
        return results

    def test_no_inline_import_struct(self):
        """函数体内不应有 `import struct`。"""
        body_imports = self._function_body_imports(self._tree)
        struct_imports = [(n, l) for n, l in body_imports if n == "struct"]
        assert not struct_imports, (
            f"发现内联 `import struct`（应移至模块顶部）: {struct_imports}"
        )

    def test_no_inline_import_math(self):
        """函数体内不应有 `import math`。"""
        body_imports = self._function_body_imports(self._tree)
        math_imports = [(n, l) for n, l in body_imports if n == "math"]
        assert not math_imports, (
            f"发现内联 `import math`（应移至模块顶部）: {math_imports}"
        )

    def test_no_inline_import_os(self):
        """函数体内不应有 `__import__('os')`。"""
        source = self._source
        assert "__import__('os')" not in source and '__import__("os")' not in source, (
            "发现内联 `__import__('os')`（应改为模块顶部 `import os`）"
        )

    def test_module_level_struct_import(self):
        """模块顶部应有 `import struct`。"""
        module_imports = []
        for node in ast.iter_child_nodes(self._tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_imports.append(alias.name)
        assert "struct" in module_imports, "模块顶部缺少 `import struct`"

    def test_module_level_os_import(self):
        """模块顶部应有 `import os`。"""
        module_imports = []
        for node in ast.iter_child_nodes(self._tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_imports.append(alias.name)
        assert "os" in module_imports, "模块顶部缺少 `import os`"


# ---------------------------------------------------------------------------
# 测试 2: serialize_bits 行为验证
# ---------------------------------------------------------------------------

class TestSerializeBits:
    """验证 serialize_bits 序列化行为与 UE FArchive::SerializeBits 一致。"""

    @pytest.fixture()
    def archive_le(self):
        """创建 LE 模式 ByteArchive。"""
        # 延迟导入，避免在模块加载时触发 inline import 问题
        from uasset_read.archive import ByteArchive
        return ByteArchive(b'\x00' * 256)

    @pytest.fixture()
    def archive_be(self):
        """创建 BE 模式 ByteArchive。"""
        from uasset_read.archive import ByteArchive
        ar = ByteArchive(b'\x00' * 256)
        ar.set_byte_swapping(True)
        return ar

    def test_byte_count_8_bits(self, archive_le):
        """8 bits → 1 byte。"""
        result = archive_le.serialize_bits(0xFF, 8)
        assert len(result) == 1

    def test_byte_count_9_bits(self, archive_le):
        """9 bits → 2 bytes（向上取整）。"""
        result = archive_le.serialize_bits(0x1FF, 9)
        assert len(result) == 2

    def test_byte_count_1_bit(self, archive_le):
        """1 bit → 1 byte。"""
        result = archive_le.serialize_bits(1, 1)
        assert len(result) == 1

    def test_byte_count_16_bits(self, archive_le):
        """16 bits → 2 bytes。"""
        result = archive_le.serialize_bits(0xFFFF, 16)
        assert len(result) == 2

    def test_byte_count_32_bits(self, archive_le):
        """32 bits → 4 bytes。"""
        result = archive_le.serialize_bits(0xFFFFFFFF, 32)
        assert len(result) == 4

    def test_value_correctness_le(self, archive_le):
        """LE 模式：值应以小端序编码。"""
        result = archive_le.serialize_bits(0x0102, 16)
        assert result == b'\x02\x01'

    def test_value_correctness_be(self, archive_be):
        """BE 模式：值应以大端序编码。"""
        result = archive_be.serialize_bits(0x0102, 16)
        assert result == b'\x01\x02'

    def test_value_truncation_non_aligned(self, archive_le):
        """非字节对齐位数：高位应被截断（UE bitmask 行为）。

        UE FArchive::SerializeBits 在加载时执行:
            ((uint8*)V)[LengthBits / 8] &= ((1 << (LengthBits & 7)) - 1)

        对于 3 bits，mask = (1 << 3) - 1 = 0x07。
        值 0xFF 应被截断为 0x07（仅保留低 3 位）。
        """
        result = archive_le.serialize_bits(0xFF, 3)
        # 1 byte, 值应为 0xFF & 0x07 = 0x07
        assert result == b'\x07'

    def test_value_5_bits(self, archive_le):
        """5 bits: mask = 0x1F。"""
        result = archive_le.serialize_bits(0xFF, 5)
        assert result == b'\x1F'

    def test_value_1_bit_true(self, archive_le):
        """1 bit 值为 1。"""
        result = archive_le.serialize_bits(1, 1)
        assert result == b'\x01'

    def test_value_1_bit_zero(self, archive_le):
        """1 bit 值为 0。"""
        result = archive_le.serialize_bits(0, 1)
        assert result == b'\x00'

    def test_value_zero(self, archive_le):
        """全零值。"""
        result = archive_le.serialize_bits(0, 8)
        assert result == b'\x00'

    def test_no_math_dependency(self):
        """serialize_bits 不应依赖 math 模块（用整数除法替代）。"""
        from uasset_read.archive import ByteArchive
        # 确保方法可正常调用（不抛 ImportError）
        ar = ByteArchive(b'\x00' * 16)
        result = ar.serialize_bits(42, 7)
        assert isinstance(result, bytes)
