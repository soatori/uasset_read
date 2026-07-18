"""batch 同 stem 覆盖测试 — #278

当 Same.uasset 和 Same.umap 同时出现在批量目录中时，
输出文件名应包含原始扩展名（Same.uasset.json / Same.umap.json），
而非都输出到 Same.json 造成静默覆盖。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from uasset_read.core import parse_batch


_FAKE_OUTPUT = '{"status": {"status": "success"}}'


def _make_fake_uasset(path: Path) -> None:
    """创建一个假的 .uasset/.umap 文件（仅需文件名匹配 glob 即可）。"""
    path.write_bytes(b"\x00" * 128)


class TestBatchStemCollision:
    """同 stem 的 .uasset/.umap 不应覆盖彼此的输出。"""

    def test_uasset_and_umap_same_stem_produce_different_outputs(self, tmp_path: Path) -> None:
        """Same.uasset + Same.umap → Same.uasset.json + Same.umap.json"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        _make_fake_uasset(asset_dir / "Same.uasset")
        _make_fake_uasset(asset_dir / "Same.umap")

        with patch(
            "uasset_read.core.parse_single",
            return_value=_FAKE_OUTPUT,
        ):
            result = parse_batch(
                str(asset_dir),
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        # 两个文件都应成功
        assert len(result.success) == 2
        assert len(result.failed) == 0

        output_files = sorted(Path(p).name for p in result.success)
        assert output_files == ["Same.uasset.json", "Same.umap.json"]

    def test_only_uasset_still_uses_plain_name(self, tmp_path: Path) -> None:
        """仅有 .uasset 时，输出为 Stem.json（保持向后兼容）。"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        _make_fake_uasset(asset_dir / "Foo.uasset")

        with patch(
            "uasset_read.core.parse_single",
            return_value=_FAKE_OUTPUT,
        ):
            result = parse_batch(
                str(asset_dir),
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        assert len(result.success) == 1
        output_files = [Path(p).name for p in result.success]
        assert output_files == ["Foo.uasset.json"]

    def test_multiple_collisions_all_distinct(self, tmp_path: Path) -> None:
        """多组同 stem 文件均产生不同输出。"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        for stem in ("Map", "Data"):
            _make_fake_uasset(asset_dir / f"{stem}.uasset")
            _make_fake_uasset(asset_dir / f"{stem}.umap")
        # 额外一个无冲突的文件
        _make_fake_uasset(asset_dir / "Solo.uasset")

        with patch(
            "uasset_read.core.parse_single",
            return_value=_FAKE_OUTPUT,
        ):
            result = parse_batch(
                str(asset_dir),
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        assert len(result.success) == 5
        output_files = sorted(Path(p).name for p in result.success)
        expected = [
            "Data.uasset.json",
            "Data.umap.json",
            "Map.uasset.json",
            "Map.umap.json",
            "Solo.uasset.json",
        ]
        assert output_files == expected

    def test_markdown_format_stem_collision(self, tmp_path: Path) -> None:
        """markdown 格式下同 stem 碰撞同样产生不同输出。"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        _make_fake_uasset(asset_dir / "Level.uasset")
        _make_fake_uasset(asset_dir / "Level.umap")

        with patch(
            "uasset_read.core.parse_single",
            return_value="# Level",
        ):
            result = parse_batch(
                str(asset_dir),
                format="markdown",
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        assert len(result.success) == 2
        output_files = sorted(Path(p).name for p in result.success)
        assert output_files == ["Level.uasset.md", "Level.umap.md"]

    def test_output_files_actually_written(self, tmp_path: Path) -> None:
        """确认输出文件确实写入了不同路径（不会静默覆盖）。"""
        asset_dir = tmp_path / "assets"
        asset_dir.mkdir()
        output_dir = tmp_path / "output"

        _make_fake_uasset(asset_dir / "Same.uasset")
        _make_fake_uasset(asset_dir / "Same.umap")

        with patch(
            "uasset_read.core.parse_single",
            return_value=_FAKE_OUTPUT,
        ):
            parse_batch(
                str(asset_dir),
                output_dir=str(output_dir),
                isolate_assets=False,
            )

        # 两个输出文件应同时存在
        assert (output_dir / "Same.uasset.json").exists()
        assert (output_dir / "Same.umap.json").exists()
        # 确认没有 Same.json（旧行为的残留）
        assert not (output_dir / "Same.json").exists()
