"""parse_uasset 安全测试"""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import _find_parent_asset_file


class TestFindParentAssetFileSecurity:
    """_find_parent_asset_file 路径遍历防护测试"""

    def test_rejects_path_traversal_with_dotdot(self, tmp_path):
        """拒绝包含 .. 的 parent_class"""
        normal_file = tmp_path / "Normal.uasset"
        normal_file.write_bytes(b"\x00" * 10)

        result = _find_parent_asset_file(
            parent_class="../../../etc/passwd",
            roots=[tmp_path]
        )

        assert result is None

    def test_rejects_path_traversal_with_slash(self, tmp_path):
        """拒绝包含 / 的 parent_class"""
        result = _find_parent_asset_file(
            parent_class="/Script/Engine/Actor",
            roots=[tmp_path]
        )
        assert result is None

    def test_rejects_path_traversal_with_backslash(self, tmp_path):
        """拒绝包含 \\ 的 parent_class"""
        result = _find_parent_asset_file(
            parent_class="..\\..\\Windows\\System32",
            roots=[tmp_path]
        )
        assert result is None

    def test_accepts_valid_class_name(self, tmp_path):
        """接受合法的类名"""
        valid_file = tmp_path / "MyParentClass.uasset"
        valid_file.write_bytes(b"\x00" * 10)

        result = _find_parent_asset_file(
            parent_class="MyParentClass",
            roots=[tmp_path]
        )

        assert result is not None
        assert result.name == "MyParentClass.uasset"

    def test_rejects_match_resolving_outside_root(self, tmp_path):
        """拒绝 root 内指向外部文件的匹配结果。"""
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        outside_file = outside / "ExternalParent.uasset"
        outside_file.write_bytes(b"\x00" * 10)
        link = root / "ExternalParent.uasset"
        try:
            link.symlink_to(outside_file)
        except OSError as exc:
            pytest.skip(f"symlink unavailable in this environment: {exc}")

        result = _find_parent_asset_file(
            parent_class="ExternalParent",
            roots=[root],
        )

        assert result is None
