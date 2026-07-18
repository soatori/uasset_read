"""批量解析混合模式测试。"""
from __future__ import annotations

import io
import json
import logging
import os
import queue
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read import project_logging
from uasset_read.batch_worker import BatchWorkerRequest, run_isolated_asset
from uasset_read.core import parse_batch
from uasset_read.memory_safety import ResourceLimits


# ---------------------------------------------------------------------------
# TestHybridIsolation — #346 智能混合模式测试
# ---------------------------------------------------------------------------

class TestHybridIsolation:
    """#346: 智能混合模式测试。"""

    def test_small_files_not_isolated(self):
        """小文件（< 20MB）应走非隔离路径。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        # 10MB 文件
        result = should_isolate(10 * 1024 * 1024, FileSizeTier.SMALL)
        assert result is False

    def test_large_files_isolated(self):
        """大文件（> 100MB）应走隔离路径。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(200 * 1024 * 1024, FileSizeTier.LARGE)
        assert result is True

    def test_file_size_tier_auto_selection(self):
        """FileSizeTier.from_size 应根据文件大小返回正确分级。"""
        from uasset_read.memory_safety import FileSizeTier

        assert FileSizeTier.from_size(10 * 1024 * 1024) == FileSizeTier.SMALL  # 10MB
        assert FileSizeTier.from_size(50 * 1024 * 1024) == FileSizeTier.MEDIUM  # 50MB
        assert FileSizeTier.from_size(150 * 1024 * 1024) == FileSizeTier.LARGE  # 150MB

    def test_medium_file_below_threshold_not_isolated(self):
        """中等文件（< 50MB）不应隔离。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(30 * 1024 * 1024, FileSizeTier.MEDIUM)  # 30MB
        assert result is False

    def test_medium_file_above_threshold_isolated(self):
        """中等文件（>= 50MB）应隔离。"""
        from uasset_read.memory_safety import should_isolate, FileSizeTier

        result = should_isolate(60 * 1024 * 1024, FileSizeTier.MEDIUM)  # 60MB
        assert result is True

    def test_auto_mode_integration(self):
        """parse_batch auto 模式应调用 should_isolate 决定隔离策略。"""
        import logging
        from uasset_read.core import parse_batch
        from pathlib import Path, PurePosixPath

        # 保存 uasset_read logger 的日志配置状态
        ua_logger = logging.getLogger("uasset_read")
        old_handlers = ua_logger.handlers[:]
        old_propagate = ua_logger.propagate
        old_level = ua_logger.level

        fake_file = PurePosixPath('/tmp/fake/test.uasset')
        try:
            with patch.object(Path, 'is_dir', return_value=True):
                with patch.object(Path, 'rglob', side_effect=[
                    [fake_file],  # *.uasset
                    [],           # *.umap
                ]):
                    with patch('uasset_read.memory_safety.get_memory_stats') as mock_stats:
                        mock_stats.return_value = MagicMock(usage_percent=0.1)
                        with patch('uasset_read.memory_safety.check_file_size', return_value=10 * 1024 * 1024):
                            with patch('uasset_read.memory_safety.FileSizeTier') as mock_tier:
                                mock_tier.from_size.return_value = 'SMALL'
                                with patch('uasset_read.memory_safety.should_isolate', return_value=False) as mock_should:
                                    with patch('uasset_read.core.parse_single') as mock_parse:
                                        mock_parse.return_value = MagicMock()
                                        mock_parse.return_value.status = 'success'
                                        parse_batch(
                                            '/tmp/fake',
                                            isolate_assets="auto",
                                        )
                                        mock_should.assert_called()
        finally:
            # 恢复 uasset_read logger 的日志配置状态，避免污染其他测试
            ua_logger.handlers = old_handlers
            ua_logger.propagate = old_propagate
            ua_logger.level = old_level


def test_auto_mode_integration_does_not_configure_logging():
    """test_auto_mode_integration 不应触发全局日志配置。"""
    ua_logger = logging.getLogger("uasset_read")
    old_handlers = ua_logger.handlers[:]
    old_propagate = ua_logger.propagate
    old_level = ua_logger.level

    from uasset_read.core import parse_batch
    from pathlib import PurePosixPath

    fake_file = PurePosixPath('/tmp/fake/test.uasset')
    try:
        with patch.object(Path, 'is_dir', return_value=True):
            with patch.object(Path, 'rglob', side_effect=[
                [fake_file],  # *.uasset
                [],           # *.umap
            ]):
                with patch('uasset_read.memory_safety.get_memory_stats') as mock_stats:
                    mock_stats.return_value = MagicMock(usage_percent=0.1)
                    with patch('uasset_read.memory_safety.check_file_size', return_value=10 * 1024 * 1024):
                        with patch('uasset_read.memory_safety.FileSizeTier') as mock_tier:
                            mock_tier.from_size.return_value = 'SMALL'
                            with patch('uasset_read.memory_safety.should_isolate', return_value=False):
                                with patch('uasset_read.core.parse_single') as mock_parse:
                                    mock_parse.return_value = MagicMock()
                                    mock_parse.return_value.status = 'success'
                                    parse_batch(
                                        '/tmp/fake',
                                        isolate_assets="auto",
                                    )
    finally:
        # 恢复 uasset_read logger 的日志配置状态，避免污染其他测试
        ua_logger.handlers = old_handlers
        ua_logger.propagate = old_propagate
        ua_logger.level = old_level

    # 验证 uasset_read logger 的 propagate 未被修改
    assert ua_logger.handlers == old_handlers
    assert ua_logger.propagate == old_propagate
    assert ua_logger.level == old_level


def test_parse_batch_invalid_isolate_assets():
    """parse_batch 应拒绝无效的 isolate_assets 值。"""
    from uasset_read.core import parse_batch
    from pathlib import Path

    with patch.object(Path, 'is_dir', return_value=True):
        with patch.object(Path, 'rglob', side_effect=[[], []]):
            with pytest.raises(ValueError, match="isolate_assets must be"):
                parse_batch(
                    '/tmp/fake',
                    isolate_assets="invalid_value",
                )


# ---------------------------------------------------------------------------
# Tests for batch worker error logging (#414)
# ---------------------------------------------------------------------------

def test_monitor_worker_logs_stderr_on_empty_result(caplog):
    """When result_queue.get() raises queue.Empty, stderr should be logged."""
    from uasset_read.batch_worker import _monitor_worker
    from uasset_read.memory_safety import ResourceLimits

    # Create a mock process that has already exited
    mock_process = MagicMock()
    mock_process.is_alive.return_value = False
    mock_process.exitcode = 1
    mock_process.pid = 12345
    mock_process.stderr_text = "TestError: something went wrong\n"

    # result_queue.get() will raise queue.Empty
    mock_queue = MagicMock()
    mock_queue.get.side_effect = queue.Empty

    limits = ResourceLimits(timeout_seconds=10, rss_limit_mb=1024)

    with caplog.at_level(logging.ERROR):
        result = _monitor_worker(
            process=mock_process,
            result_queue=mock_queue,
            limits=limits,
            poll_interval_seconds=0.01,
        )

    assert result.succeeded is False
    assert "TestError: something went wrong" in result.error_details
    assert "worker_exit" in result.error
    # Check that stderr was logged
    assert any("TestError: something went wrong" in record.message for record in caplog.records)


def test_monitor_worker_includes_stderr_in_outcome():
    """When result_queue.get() raises queue.Empty, stderr should be in outcome."""
    from uasset_read.batch_worker import _monitor_worker
    from uasset_read.memory_safety import ResourceLimits

    mock_process = MagicMock()
    mock_process.is_alive.return_value = False
    mock_process.exitcode = 1
    mock_process.pid = 12345
    mock_process.stderr_text = "ImportError: No module named 'foo'\n"

    mock_queue = MagicMock()
    mock_queue.get.side_effect = queue.Empty

    limits = ResourceLimits(timeout_seconds=10, rss_limit_mb=1024)

    result = _monitor_worker(
        process=mock_process,
        result_queue=mock_queue,
        limits=limits,
        poll_interval_seconds=0.01,
    )

    assert result.succeeded is False
    assert "ImportError: No module named 'foo'" in result.error_details


# ---------------------------------------------------------------------------
# Tests for batch worker startup behavior (#415)
# ---------------------------------------------------------------------------

def test_batch_worker_no_runtime_warning():
    """batch worker 启动不应触发 RuntimeWarning"""
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read.batch_worker", "--help"],
        capture_output=True,
        text=True,
    )
    assert "RuntimeWarning" not in result.stderr


# ---------------------------------------------------------------------------
# batch 同 stem 覆盖测试 — #278
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Parent-side isolated worker monitoring tests
# ---------------------------------------------------------------------------

# 子进程需要 src/ 在 PYTHONPATH 中才能 import uasset_read
_SRC_DIR = str(Path(__file__).resolve().parents[2] / "src")


def test_worker_stream_logging_includes_run_process_asset_and_stage():
    stream = io.StringIO()
    handler = project_logging.configure_worker_stream_logging(
        stream=stream,
        level="DEBUG",
        run_id="run-42",
        asset="Example.uasset",
    )
    try:
        logging.getLogger("uasset_read.worker_test").warning("worker detail")
    finally:
        logging.getLogger("uasset_read").removeHandler(handler)
        handler.close()

    output = stream.getvalue()
    assert "run=run-42" in output
    assert f"pid={os.getpid()}" in output
    assert "asset=Example.uasset" in output
    assert "stage=worker" in output
    assert "worker detail" in output


def test_stderr_drain_forwards_each_worker_line():
    from uasset_read.batch_worker import _StderrDrain

    forwarded = []
    drain = _StderrDrain(line_callback=forwarded.append)

    drain._append("first\n")
    drain._append("second\n")

    assert forwarded == ["first\n", "second\n"]


class _FakeProcess:
    pid = 123
    exitcode = None

    def __init__(self) -> None:
        self.terminated = False

    def is_alive(self) -> bool:
        return not self.terminated

    def terminate(self) -> None:
        self.terminated = True

    def join(self, timeout=None) -> None:
        return None

    def kill(self) -> None:
        self.terminated = True


def test_monitor_terminates_worker_over_rss_limit() -> None:
    from uasset_read.batch_worker import _monitor_worker

    process = _FakeProcess()
    outcome = _monitor_worker(
        process=process,
        result_queue=None,
        limits=ResourceLimits(64, 30),
        poll_interval_seconds=0,
        rss_reader=lambda _pid: 65,
        monotonic=lambda: 0,
        sleep=lambda _seconds: None,
    )

    assert process.terminated is True
    assert outcome.succeeded is False
    assert outcome.error == "memory_limit: 65.0MB > 64.0MB"


def test_monitor_terminates_worker_after_timeout() -> None:
    from uasset_read.batch_worker import _monitor_worker

    process = _FakeProcess()
    times = iter([0.0, 11.0])
    outcome = _monitor_worker(
        process=process,
        result_queue=None,
        limits=ResourceLimits(64, 10),
        poll_interval_seconds=0,
        rss_reader=lambda _pid: 1,
        monotonic=lambda: next(times),
        sleep=lambda _seconds: None,
    )

    assert process.terminated is True
    assert outcome.succeeded is False
    assert outcome.error == "timeout: 11.0s > 10.0s"


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="Per-process RSS monitoring requires psutil on macOS"
)
def test_spawn_worker_writes_output_atomically(tmp_path) -> None:
    asset = tmp_path / "invalid.uasset"
    output = tmp_path / "out" / "invalid.json"
    asset.write_bytes(b"\x00" * 100)
    request = BatchWorkerRequest(
        file_path=str(asset),
        output_path=str(output),
        parse_options={"format": "json", "tolerant": True},
    )

    # 子进程需要 PYTHONPATH 才能 import uasset_read
    old_pythonpath = os.environ.get("PYTHONPATH")
    try:
        existing = os.environ.get("PYTHONPATH", "")
        os.environ["PYTHONPATH"] = _SRC_DIR + os.pathsep + existing if existing else _SRC_DIR
        outcome = run_isolated_asset(
            request,
            limits=ResourceLimits(512, 30),
            poll_interval_seconds=0.01,
        )
    finally:
        if old_pythonpath is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = old_pythonpath

    assert outcome.succeeded is True
    assert outcome.output_path == str(output)
    assert json.loads(output.read_text(encoding="utf-8"))["status"]["status"] == "failed"
    assert list(output.parent.glob(".*.tmp")) == []


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="Per-process RSS monitoring requires psutil on macOS"
)
def test_parse_batch_works_in_script_without_main_guard(tmp_path) -> None:
    """验证 parse_batch 可在无 if __name__ == '__main__' 守卫的脚本中调用。"""
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "invalid.uasset").write_bytes(b"\x00" * 100)
    script = tmp_path / "call_batch.py"
    script.write_text(
        "from uasset_read import parse_batch\n"
        f"result = parse_batch({str(asset_dir)!r})\n"
        "print(len(result.success), len(result.failed))\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = _SRC_DIR

    completed = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    # 无效 uasset 文件在 isolated 模式下容忍解析成功，输出 JSON 并计入 success
    assert completed.stdout.strip() == "1 0"
