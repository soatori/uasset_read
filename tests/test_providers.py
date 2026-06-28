"""GameDirectoryProvider 单元测试 — 验证游戏目录自动扫描功能。"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.providers import GameDirectoryProvider


# 测试样本根目录（使用较小的子目录避免扫描全量 20K+ 文件）
SAMPLES_ROOT = Path("E:/Develop/lib/Samples")
SMALL_PROJECT = Path("E:/Develop/lib/Samples/LyraStarterGame")


# ============================================================================
# 初始化测试
# ============================================================================


class TestGameDirectoryProviderInit:
    """GameDirectoryProvider 初始化测试。"""

    def test_game_directory_provider_init(self):
        """初始化测试 — 验证有效的游戏目录可以成功初始化。"""
        provider = GameDirectoryProvider(SAMPLES_ROOT)
        assert provider.root == SAMPLES_ROOT.resolve()

    def test_init_with_string_path(self):
        """使用字符串路径初始化。"""
        provider = GameDirectoryProvider(str(SAMPLES_ROOT))
        assert provider.root == SAMPLES_ROOT.resolve()

    def test_init_with_path_object(self):
        """使用 Path 对象初始化。"""
        provider = GameDirectoryProvider(SAMPLES_ROOT)
        assert isinstance(provider.root, Path)

    def test_init_nonexistent_directory(self):
        """不存在的目录应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            GameDirectoryProvider("E:/Develop/nonexistent_directory_xyz")

    def test_init_with_file_path(self):
        """文件路径（非目录）应抛出 NotADirectoryError。"""
        with pytest.raises(NotADirectoryError):
            GameDirectoryProvider(SAMPLES_ROOT / "README.md" if (SAMPLES_ROOT / "README.md").exists()
                                 else SAMPLES_ROOT / "StarterContent" / "contents.txt")

    def test_has_uproject_true(self):
        """检测到 .uproject 文件应返回 True。"""
        provider = GameDirectoryProvider(SAMPLES_ROOT / "Lyra")
        assert provider.has_uproject() is True

    def test_get_uproject_file(self):
        """应能获取 .uproject 文件路径。"""
        provider = GameDirectoryProvider(SAMPLES_ROOT / "Lyra")
        uproject = provider.get_uproject_file()
        assert uproject is not None
        assert uproject.suffix == ".uproject"
        assert uproject.name == "Lyra.uproject"


# ============================================================================
# 文件列出测试
# ============================================================================


class TestGameDirectoryProviderListFiles:
    """文件列表功能测试。"""

    def test_game_directory_provider_list_uassets(self):
        """列出 uasset 文件 — 验证能扫描到 .uasset 文件。"""
        provider = GameDirectoryProvider(SMALL_PROJECT)
        files = provider.list_uasset_files()
        assert len(files) > 0
        extensions = {f.suffix.lower() for f in files}
        assert ".uasset" in extensions

    def test_list_uasset_files_are_paths(self):
        """返回的每个元素都应是 Path 对象。"""
        provider = GameDirectoryProvider(SMALL_PROJECT)
        files = provider.list_uasset_files()
        for f in files:
            assert isinstance(f, Path)

    def test_list_uasset_files_sorted(self):
        """返回的文件列表应按字母顺序排序。"""
        provider = GameDirectoryProvider(SMALL_PROJECT)
        files = provider.list_uasset_files()
        assert files == sorted(files)

    def test_list_files_custom_extension(self):
        """使用自定义扩展名列出文件。"""
        provider = GameDirectoryProvider(SAMPLES_ROOT / "Lyra")
        files = provider.list_files(".uproject")
        assert len(files) == 1
        assert files[0].suffix == ".uproject"

    def test_list_files_without_dot(self):
        """扩展名不带前导点也应正常工作。"""
        provider = GameDirectoryProvider(SAMPLES_ROOT / "Lyra")
        files = provider.list_files("uproject")
        assert len(files) == 1

    def test_list_pak_files_empty(self):
        """示例目录中无 .upak 文件，应返回空列表。"""
        provider = GameDirectoryProvider(SMALL_PROJECT)
        files = provider.list_pak_files()
        assert files == []

    def test_list_utoc_files_empty(self):
        """示例目录中无 .utoc 文件，应返回空列表。"""
        provider = GameDirectoryProvider(SMALL_PROJECT)
        files = provider.list_utoc_files()
        assert files == []


# ============================================================================
# 模式匹配测试
# ============================================================================


class TestGameDirectoryProviderFindFile:
    """模式匹配功能测试。"""

    def test_find_file_by_name(self):
        """按精确文件名匹配。"""
        provider = GameDirectoryProvider(SAMPLES_ROOT / "Lyra")
        files = provider.find_file("Lyra.uproject")
        assert len(files) == 1
        assert files[0].name == "Lyra.uproject"

    def test_find_file_by_wildcard(self):
        """使用通配符匹配。"""
        provider = GameDirectoryProvider(SMALL_PROJECT)
        files = provider.find_file("*.uasset")
        assert len(files) > 0
        for f in files:
            assert f.suffix == ".uasset"

    def test_find_file_no_match(self):
        """无匹配时应返回空列表。"""
        provider = GameDirectoryProvider(SAMPLES_ROOT / "Lyra")
        files = provider.find_file("nonexistent_*.xyz")
        assert files == []

    def test_find_file_sorted(self):
        """匹配结果应按字母顺序排序。"""
        provider = GameDirectoryProvider(SMALL_PROJECT)
        files = provider.find_file("*.uasset")
        assert files == sorted(files)
