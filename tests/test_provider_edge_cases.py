"""Tests for GameDirectoryProvider edge cases — bounded adversarial fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.providers import GameDirectoryProvider


class TestProviderEdgeCases:
    """Verify GameDirectoryProvider handles edge cases correctly."""

    def test_nonexistent_directory_raises(self, tmp_path: Path):
        """Provider must raise FileNotFoundError for non-existent directory."""
        with pytest.raises(FileNotFoundError):
            GameDirectoryProvider(tmp_path / "nonexistent")

    def test_file_path_raises(self, tmp_path: Path):
        """Provider must raise NotADirectoryError for a file path."""
        f = tmp_path / "test.uasset"
        f.write_bytes(b"\x00" * 100)
        with pytest.raises(NotADirectoryError):
            GameDirectoryProvider(f)

    def test_empty_directory_returns_no_files(self, tmp_path: Path):
        """Provider must return empty list for empty directory."""
        provider = GameDirectoryProvider(tmp_path)
        assert provider.list_files(".uasset") == []
        assert provider.list_files(".umap") == []

    def test_directory_with_no_uassets(self, tmp_path: Path):
        """Provider must return empty list when no .uasset files exist."""
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.json").write_text("{}")
        provider = GameDirectoryProvider(tmp_path)
        assert provider.list_files(".uasset") == []

    def test_extension_with_or_without_dot(self, tmp_path: Path):
        """Provider must handle extensions with or without leading dot."""
        (tmp_path / "test.uasset").write_bytes(b"\x00" * 100)
        provider = GameDirectoryProvider(tmp_path)
        assert len(provider.list_files("uasset")) == 1
        assert len(provider.list_files(".uasset")) == 1

    def test_case_insensitive_extension(self, tmp_path: Path):
        """Provider must match extensions case-insensitively."""
        (tmp_path / "test.UASSET").write_bytes(b"\x00" * 100)
        (tmp_path / "test2.uasset").write_bytes(b"\x00" * 100)
        provider = GameDirectoryProvider(tmp_path)
        assert len(provider.list_files(".uasset")) == 2

    def test_nested_directories(self, tmp_path: Path):
        """Provider must scan subdirectories recursively."""
        sub = tmp_path / "Content" / "Blueprints"
        sub.mkdir(parents=True)
        (sub / "test.uasset").write_bytes(b"\x00" * 100)
        (tmp_path / "root.uasset").write_bytes(b"\x00" * 100)
        provider = GameDirectoryProvider(tmp_path)
        files = provider.list_files(".uasset")
        assert len(files) == 2

    def test_uproject_detection(self, tmp_path: Path):
        """Provider must detect .uproject files."""
        provider = GameDirectoryProvider(tmp_path)
        assert provider.has_uproject() is False
        assert provider.get_uproject_file() is None

        (tmp_path / "MyGame.uproject").write_text("{}")
        assert provider.has_uproject() is True
        assert provider.get_uproject_file() is not None

    def test_list_files_sorted(self, tmp_path: Path):
        """Provider must return files sorted alphabetically."""
        for name in ["c.uasset", "a.uasset", "b.uasset"]:
            (tmp_path / name).write_bytes(b"\x00" * 100)
        provider = GameDirectoryProvider(tmp_path)
        files = provider.list_files(".uasset")
        names = [f.name for f in files]
        assert names == sorted(names)
