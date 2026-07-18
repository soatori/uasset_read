"""Parent-side isolated worker monitoring tests."""

from __future__ import annotations

import json
import io
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from uasset_read.batch_worker import BatchWorkerRequest, BatchWorkerOutcome, run_isolated_asset
from uasset_read.memory_safety import ResourceLimits
from uasset_read import project_logging

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


def test_batch_worker_outcome_includes_error_details():
    """验证 BatchWorkerOutcome.error_details 包含完整错误信息"""
    outcome = BatchWorkerOutcome(
        succeeded=False,
        error="ValueError: Invalid property tag",
        error_details="Traceback (most recent call last):\n  File ...\nValueError: Invalid property tag at offset 1234"
    )
    assert outcome.error_details  # 不为空
    assert "Traceback" in outcome.error_details  # 包含堆栈
