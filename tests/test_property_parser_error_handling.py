"""tests/test_property_parser_error_handling.py — 异常处理日志验证

验证 property_parser.py 中 8 处 except Exception: pass 已被替换为带日志的 handler，
以及 archive.py 中添加了 MemoryError 处理。

采用源码级别验证：检查代码中包含预期的 logger 调用而非裸 pass。
"""
import ast
import re


def read_source(module_path: str) -> str:
    """读取源码文件内容。"""
    with open(module_path, "r", encoding="utf-8") as f:
        return f.read()


class TestPropertyParserErrorLogging:
    """验证 property_parser.py 中的异常处理改进。"""

    def test_binary_or_native_handler_has_logging(self):
        """BinaryOrNative handler 应包含 logger.warning 调用。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        # 查找 BinaryOrNative handler 块
        assert "BinaryOrNative handler failed" in source
        assert 'logger.warning("BinaryOrNative handler failed' in source

    def test_custom_property_fd_handler_has_logging(self):
        """CustomProperty_FD handler 应包含 logger.warning 调用。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        assert "Custom property handler (0x%02X) failed" in source
        assert 'logger.warning("Custom property handler (0x%02X) failed' in source

    def test_game_specific_custom_handler_has_logging(self):
        """游戏特定 custom handler 应包含 logger.warning 调用。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        assert "Game-specific custom property handler failed" in source
        assert 'logger.warning("Game-specific custom property handler failed' in source

    def test_resolve_class_name_export_has_logging(self):
        """parse_properties_from_export 中 resolve_class_name 应有 debug 日志。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Failed to resolve class name for export' in source

    def test_resolve_class_name_property_loop_has_logging(self):
        """属性循环中 resolve_class_name 应有 debug 日志。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Failed to resolve class name in property loop' in source

    def test_resolve_mapping_struct_name_has_logging(self):
        """_resolve_mapping_struct_name 应有 debug 日志。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Failed to resolve mapping struct name' in source

    def test_unversioned_header_parse_has_logging(self):
        """_try_read_unversioned_header 应有 debug 日志。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Unversioned header parse failed' in source

    def test_unversioned_variable_size_has_logging(self):
        """_estimate_unversioned_variable_size 应有 debug 日志。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Unversioned variable size estimation failed' in source

    def test_no_bare_except_exception_pass(self):
        """验证不再存在裸的 except Exception: pass。"""
        source = read_source("src/uasset_read/parsers/property_parser.py")
        # 检查不应存在的模式（except Exception 后直接 pass）
        bare_pattern = r"except\s+Exception\s*:\s*pass\s*#\s*解析失败|except\s+Exception\s*:\s*pass\s*#\s*fallback"
        matches = re.findall(bare_pattern, source)
        assert len(matches) == 0, f"发现裸 except Exception: pass: {matches}"


class TestArchiveMemoryErrorHandling:
    """验证 archive.py 中的 MemoryError 处理。"""

    def test_mmap_includes_memory_error(self):
        """mmap 异常处理应包含 MemoryError。"""
        source = read_source("src/uasset_read/archive.py")
        assert "MemoryError" in source
        assert "(OSError, ValueError, PermissionError, MemoryError)" in source


class TestErrorHandlingIntegration:
    """集成测试：验证异常处理不破坏现有功能。"""

    def test_parse_property_value_with_bad_binary_or_native(self):
        """BinaryOrNative handler 失败时应回退到 raw bytes 而不崩溃。"""
        from io import BytesIO
        from unittest.mock import MagicMock
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(
            name="TestProp",
            type="MaterialInput",
            size=4,
            serialize_type="BinaryOrNative",
        )

        # 创建 mock archive
        archive = MagicMock()
        archive.read.return_value = b"\xFF\xFF\xFF\xFF"
        archive.tell.return_value = 0

        # 不应抛出异常
        result = parse_property_value(tag, archive, [], [])
        assert result is not None
        assert result.get("kind") == "binary_or_native_property"

    def test_resolve_mapping_struct_name_fallback(self):
        """_resolve_mapping_struct_name 失败时应返回 fallback 名称。"""
        from dataclasses import dataclass
        from uasset_read.parsers.property_parser import _resolve_mapping_struct_name

        @dataclass
        class FakeExport:
            object_name: str = "FallbackExport"
            class_index: int = -999

        export = FakeExport()
        result = _resolve_mapping_struct_name(export, [], [])

        # 应返回 object_name 作为 fallback
        assert result == "FallbackExport"
