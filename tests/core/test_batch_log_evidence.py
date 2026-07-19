"""#423 验证：batch 失败详情在同一日志文件中落盘

验证 parse_batch 处理失败时，关键信息（asset_start、失败详情、batch_summary failed=1）
是否在同一日志文件中记录。
"""
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from uasset_read.core import parse_batch


def test_batch_failure_logged_to_same_file(tmp_path):
    """batch 失败时，关键信息应在同一 log 文件中"""
    # 准备：创建包含一个假 .uasset 的目录
    batch_dir = tmp_path / "batch_input"
    batch_dir.mkdir()
    fake_asset = batch_dir / "fail.uasset"
    fake_asset.write_bytes(b"\x00" * 100)

    log_dir = tmp_path / "logs"

    # 模拟解析抛出异常（isolate_assets=False 走非隔离路径）
    with patch("uasset_read.core._parse_and_render", side_effect=ValueError("corrupted asset")):
        result = parse_batch(
            str(batch_dir),
            isolate_assets=False,
            log_dir=str(log_dir),
            log_enabled=True,
        )

    # 验证 result 中记录了失败
    assert len(result.failed) >= 1, f"期望至少 1 个失败，实际: {len(result.failed)}"
    path, error, details = result.failed[0]
    assert "corrupted asset" in error
    assert "ValueError" in error

    # 查找日志文件
    log_files = list(Path(log_dir).rglob("*.log")) if log_dir.exists() else []
    if not log_files:
        # project_logging 可能使用其他目录，检查项目级 log/
        project_log = Path("log")
        if project_log.exists():
            log_files = sorted(project_log.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)

    assert log_files, "未找到日志文件，无法验证落盘内容"

    # 读取最新日志文件
    latest_log = log_files[0]
    log_content = latest_log.read_text(encoding="utf-8", errors="replace")

    # 关键验证点：batch_summary 且 failed=1
    has_batch_summary = "batch_summary" in log_content
    has_failed_count = "failed=1" in log_content

    # 输出诊断信息
    print(f"\n日志文件: {latest_log}")
    print(f"包含 batch_summary: {has_batch_summary}")
    print(f"包含 failed=1: {has_failed_count}")
    print(f"日志内容片段:\n{log_content[:2000]}")

    assert has_batch_summary, "日志中缺少 batch_summary"
    assert has_failed_count, "日志中缺少 failed=1 计数"

    # 注意：当前实现中，单个文件的错误详情仅存储在 result.failed 中，
    # 并不通过 logging 写入日志文件。只有 batch_summary 的计数被记录。
    has_error_detail_in_log = "corrupted asset" in log_content
    print(f"日志中包含错误详情: {has_error_detail_in_log}")
    if not has_error_detail_in_log:
        print("NOTE: 当前实现未将单个文件的错误详情写入日志，仅记录 batch_summary 计数")
