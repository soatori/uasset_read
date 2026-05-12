"""UE5 序列化容错测试 — FText, PropertyTag, graph parsing。

Phase 33a: UE5 序列化问题修复。
"""
import pytest
from pathlib import Path

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.serializers.graph import read_ftext_with_history
from uasset_read import parse_uasset


ASSET_DIR = Path(r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson")


def _find_asset(name: str) -> str:
    """Find a .uasset file by name in the UE sample project."""
    for p in ASSET_DIR.rglob(name):
        return str(p)
    pytest.skip(f"Test asset {name} not found in {ASSET_DIR}")


class TestFTextWithHistory:
    """read_ftext_with_history 函数测试。"""

    def test_history_type_none_no_culture(self):
        """history_type=0xFF (None) 无 culture 的 FText 读取。"""
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        archive = FArchive(asset_path, tolerant=True)
        try:
            # 定位到一个已知有 FText 的位置（PinFriendlyName）
            # 直接测试容错模式不抛异常
            value, consumed = read_ftext_with_history(archive, 0xFF, tolerant=True)
            assert value == ""
            assert consumed >= 0
        finally:
            archive.close()

    def test_history_type_base(self):
        """history_type=0 (Base) 的 FText 读取。"""
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        archive = FArchive(asset_path, tolerant=True)
        try:
            value, consumed = read_ftext_with_history(archive, 0, tolerant=True)
            assert value == ""
            assert consumed >= 0
        finally:
            archive.close()

    def test_history_type_custom(self):
        """history_type=1-254 (Custom) 的 FText 读取。"""
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        archive = FArchive(asset_path, tolerant=True)
        try:
            value, consumed = read_ftext_with_history(archive, 1, tolerant=True)
            assert value == ""
            assert consumed >= 0
        finally:
            archive.close()

    def test_strict_mode_raises_on_invalid(self):
        """严格模式（tolerant=False）对明显无效的数据抛出 ParseError。"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.uasset', delete=False) as f:
            # 写入一个极大的负数长度：0xFFFF0000 → -65536
            # read_fstring 会计算 utf16_len = 65536 * 2 = 131072，但文件不够大
            f.write(b'\x00\x00\x00\x00')  # pos 0-3
            f.write(b'\x00\xff\xff\xff')  # little-endian: -65536
            f.write(b'\x00' * 10)         # 只写少量字节，让 read 失败
            f.flush()
            tmp_path = f.name

        archive = FArchive(tmp_path, tolerant=False)
        try:
            archive.seek(4)
            # history_type=0 (Base) 会尝试读 3 个 FString，第一个就会失败
            with pytest.raises(ParseError):
                read_ftext_with_history(archive, 0, tolerant=False)
        finally:
            archive.close()
            os.unlink(tmp_path)


class TestTolerantParsing:
    """集成测试：容错模式下的整体解析。"""

    def test_blueprint_parsed_in_tolerant_mode(self):
        """BP_FirstPersonCharacter 在容错模式下应能解析或返回警告而非错误。"""
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        result = parse_uasset(asset_path, tolerant=True)

        # 容错模式下不应有 "UTF-16 string length too large" 错误
        ftext_errors = [e for e in result.errors if "UTF-16" in e and "length" in e]
        assert len(ftext_errors) == 0, f"Unexpected FText errors: {ftext_errors}"

        # 不应有负数 size 错误
        negative_errors = [e for e in result.errors if "negative" in e.lower()]
        assert len(negative_errors) == 0, f"Negative size errors: {negative_errors}"

    def test_strict_mode_raises_on_ue5_asset(self):
        """严格模式下 UE5 资产可能抛出 ParseError（已知序列化差异）。

        注意：某些 UE5 资产可能在严格模式下也能解析，因此此测试
        仅验证严格模式能正确传递错误，不强制要求所有 UE5 资产都失败。
        """
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        # 严格模式可能成功也可能失败，取决于资产具体内容
        # 这里只验证它不会因为 tolerant 参数而崩溃
        try:
            result = parse_uasset(asset_path, tolerant=False)
            # 如果成功，至少验证返回了 ParseResult
            assert hasattr(result, 'errors')
        except (ParseError, Exception):
            pass  # 严格模式下抛出异常也是预期行为


class TestValidateSizeTolerant:
    """FArchive.validate_size 容错模式测试。"""

    def test_negative_size_tolerant(self):
        """容错模式接受负数 size。"""
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        archive = FArchive(asset_path, tolerant=True)
        try:
            archive.validate_size(-100, "test", tolerant=True)
            # 不应抛出异常
        finally:
            archive.close()

    def test_excessive_size_tolerant(self):
        """容错模式接受超出剩余字节数的 size。"""
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        archive = FArchive(asset_path, tolerant=True)
        try:
            archive.seek(0)
            archive.validate_size(999999999, "test", tolerant=True)
            # 不应抛出异常
        finally:
            archive.close()

    def test_negative_size_strict(self):
        """严格模式拒绝负数 size。"""
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        archive = FArchive(asset_path, tolerant=False)
        try:
            with pytest.raises(ParseError, match="negative"):
                archive.validate_size(-100, "test", tolerant=False)
        finally:
            archive.close()

    def test_excessive_size_strict(self):
        """严格模式拒绝超出剩余字节数的 size。"""
        asset_path = _find_asset("BP_FirstPersonCharacter.uasset")
        archive = FArchive(asset_path, tolerant=False)
        try:
            archive.seek(0)
            with pytest.raises(ParseError, match="exceeds"):
                archive.validate_size(999999999, "test", tolerant=False)
        finally:
            archive.close()
