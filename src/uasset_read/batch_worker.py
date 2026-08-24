"""Subprocess-isolated per-asset worker for :func:`uasset_read.core.parse_batch`."""

import argparse
import collections
import json
import logging
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

# 抑制 runpy 的 RuntimeWarning — 当通过 `python -m uasset_read.batch_worker` 启动时，
# runpy 先导入包再执行模块，导致 "found in sys.modules after import" 警告
warnings.filterwarnings(
    "ignore",
    message=".*found in sys.modules after import.*",
    category=RuntimeWarning,
)

logger = logging.getLogger(__name__)

from uasset_read.memory_safety import (
    MemoryPolicy,
    ResourceLimits,
    _get_process_rss_mb,
)

# stderr drain 默认上限：保留最后 1 MB 输出
_STDERR_DRAIN_MAX_BYTES = 1024 * 1024
_STDERR_DRAIN_MAX_LINES = 10_000


class _StderrDrain:
    """有界 stderr drain — 保留尾部，防止管道死锁。

    使用后台线程持续读取子进程 stderr，避免管道缓冲区填满后子进程阻塞写入
    导致父进程 ``wait()`` 永远不返回的死锁。内部使用 deque 保留最后 N 行 /
    N 字节，超出部分自动丢弃。
    """

    def __init__(
        self,
        max_bytes: int = _STDERR_DRAIN_MAX_BYTES,
        max_lines: int = _STDERR_DRAIN_MAX_LINES,
        line_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._max_bytes = max_bytes
        self._max_lines = max_lines
        self._lines: collections.deque[str] = collections.deque(maxlen=max_lines)
        self._total_bytes: int = 0
        self._dropped_count: int = 0
        self._thread: threading.Thread | None = None
        self._line_callback = line_callback

    def start(self, proc: subprocess.Popen[bytes]) -> None:
        """启动后台 drain 线程。"""
        if proc.stderr is None:
            return
        self._thread = threading.Thread(
            target=self._drain_loop,
            args=(proc,),
            daemon=True,
            name="stderr-drain",
        )
        self._thread.start()

    def _drain_loop(self, proc: subprocess.Popen[bytes]) -> None:
        """持续读取 stderr 行直到 EOF。"""
        try:
            if proc.stderr is None:
                return
            for raw_line in proc.stderr:
                line = (
                    raw_line.decode("utf-8", errors="replace")
                    if isinstance(raw_line, bytes)
                    else raw_line
                )
                self._append(line)
        except (OSError, ValueError) as exc:
            logger.debug("stderr drain 异常: %s", exc)

    def _append(self, line: str) -> None:
        """添加一行，超出字节上限时丢弃最旧行。"""
        line_bytes = len(line.encode("utf-8", errors="replace"))
        # 检查 deque 是否会自动丢弃旧行
        if self._lines.maxlen is not None and len(self._lines) >= self._lines.maxlen:
            old = self._lines[0]
            self._total_bytes -= len(old.encode("utf-8", errors="replace"))
            self._dropped_count += 1
        self._lines.append(line)
        self._total_bytes += line_bytes
        if self._line_callback is not None:
            self._line_callback(line)
        # 如果总字节数仍超限，继续丢弃旧行
        while self._total_bytes > self._max_bytes and len(self._lines) > 1:
            old = self._lines.popleft()
            self._total_bytes -= len(old.encode("utf-8", errors="replace"))
            self._dropped_count += 1

    def join(self, timeout: float | None = None) -> None:
        """等待 drain 线程完成。"""
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    @property
    def text(self) -> str:
        """返回收集到的 stderr 文本。"""
        return "".join(self._lines)

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    @property
    def total_bytes(self) -> int:
        return self._total_bytes


@dataclass(frozen=True)
class BatchWorkerRequest:
    file_path: str
    output_path: str
    parse_options: dict[str, Any]
    logging_options: dict[str, Any] | None = None


@dataclass(frozen=True)
class BatchWorkerOutcome:
    succeeded: bool
    output_path: str = ""
    error: str = ""
    error_details: str = ""


def _temporary_output_path(output_path: str | Path, pid: int) -> Path:
    output = Path(output_path)
    return output.with_name(f".{output.name}.{pid}.tmp")


def _policy_to_payload(policy: MemoryPolicy) -> dict[str, Any]:
    return {
        "small_file_max_bytes": policy.small_file_max_bytes,
        "medium_file_max_bytes": policy.medium_file_max_bytes,
        "small_limits": asdict(policy.small_limits),
        "medium_limits": asdict(policy.medium_limits),
        "large_limits": asdict(policy.large_limits),
        "system_usage_limit": policy.system_usage_limit,
        "poll_interval_seconds": policy.poll_interval_seconds,
    }


def _policy_from_payload(payload: dict[str, Any]) -> MemoryPolicy:
    return MemoryPolicy(
        small_file_max_bytes=payload["small_file_max_bytes"],
        medium_file_max_bytes=payload["medium_file_max_bytes"],
        small_limits=ResourceLimits(**payload["small_limits"]),
        medium_limits=ResourceLimits(**payload["medium_limits"]),
        large_limits=ResourceLimits(**payload["large_limits"]),
        system_usage_limit=payload["system_usage_limit"],
        poll_interval_seconds=payload["poll_interval_seconds"],
    )


def _request_to_payload(request: BatchWorkerRequest) -> dict[str, Any]:
    options = dict(request.parse_options)
    policy = options.get("memory_policy")
    if isinstance(policy, MemoryPolicy):
        options["memory_policy"] = {"__memory_policy__": _policy_to_payload(policy)}
    return {
        "file_path": request.file_path,
        "output_path": request.output_path,
        "parse_options": options,
        "logging_options": request.logging_options or {},
    }


def _request_from_payload(payload: dict[str, Any]) -> BatchWorkerRequest:
    options = dict(payload["parse_options"])
    policy = options.get("memory_policy")
    if isinstance(policy, dict) and "__memory_policy__" in policy:
        options["memory_policy"] = _policy_from_payload(policy["__memory_policy__"])
    return BatchWorkerRequest(
        file_path=payload["file_path"],
        output_path=payload["output_path"],
        parse_options=options,
        logging_options=payload.get("logging_options") or {},
    )


def _asset_worker(request: BatchWorkerRequest) -> BatchWorkerOutcome:
    """Parse and atomically publish one asset entirely inside the child."""
    from uasset_read.core import parse_single

    output_path = Path(request.output_path)
    temporary_path = _temporary_output_path(output_path, os.getpid())
    worker_handler = None
    try:
        options = dict(request.parse_options)
        logging_options = request.logging_options or {}
        if logging_options.get("enabled", True):
            from uasset_read.project_logging import configure_worker_stream_logging

            run_id = (
                logging_options.get("run_id")
                or os.environ.get("UASSET_READ_RUN_ID")
                or "-"
            )
            worker_handler = configure_worker_stream_logging(
                level=logging_options.get("level") or "DEBUG",
                run_id=run_id,
                asset=Path(request.file_path).name,
            )
        rendered = parse_single(request.file_path, **options)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(rendered, encoding="utf-8")
        os.replace(temporary_path, output_path)
        return BatchWorkerOutcome(True, str(output_path), "")
    except BaseException as exc:
        import traceback

        return BatchWorkerOutcome(
            False,
            "",
            f"{type(exc).__name__}: {exc}",
            traceback.format_exc(),
        )
    finally:
        if worker_handler is not None:
            package_logger = logging.getLogger("uasset_read")
            package_logger.removeHandler(worker_handler)
            worker_handler.close()
            package_logger.propagate = True
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError as e:
            logger.debug("清理临时文件失败: %s", e)


class _SubprocessAdapter:
    def __init__(self, process: subprocess.Popen) -> None:
        self._process = process
        self.pid = process.pid
        self._stderr_drain = _StderrDrain(line_callback=self._forward_stderr_line)
        self._stderr_drain.start(process)

    def _forward_stderr_line(self, line: str) -> None:
        rendered = line.rstrip("\r\n")
        level = logging.DEBUG
        for name in ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"):
            if f"[{name}]" in rendered:
                level = getattr(logging, name)
                break
        logger.log(level, "worker[%d] %s", self.pid, rendered)

    @property
    def exitcode(self) -> int | None:
        return self._process.poll()

    def is_alive(self) -> bool:
        return self._process.poll() is None

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()

    @property
    def stderr_text(self) -> str:
        return self._stderr_drain.text

    def join(self, timeout=None) -> None:
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.debug("子进程 join 超时，继续执行")
        # 等待 drain 线程消费完管道中剩余数据
        self._stderr_drain.join(timeout=5)


class _ResultFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, timeout: float) -> BatchWorkerOutcome:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.path.is_file():
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                return BatchWorkerOutcome(**payload)
            time.sleep(0.01)
        raise queue.Empty


def _terminate_worker(process) -> None:
    if process.is_alive():
        process.terminate()
    process.join(timeout=5)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(timeout=5)


def _monitor_worker(
    *,
    process,
    result_queue,
    limits: ResourceLimits,
    poll_interval_seconds: float,
    rss_reader: Callable[[int], float] = _get_process_rss_mb,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> BatchWorkerOutcome:
    started_at = monotonic()
    while process.is_alive():
        elapsed = monotonic() - started_at
        if elapsed > limits.timeout_seconds:
            _terminate_worker(process)
            return BatchWorkerOutcome(
                False,
                "",
                f"timeout: {elapsed:.1f}s > {limits.timeout_seconds:.1f}s",
            )

        rss_mb = rss_reader(process.pid)
        if rss_mb > limits.rss_limit_mb:
            _terminate_worker(process)
            return BatchWorkerOutcome(
                False,
                "",
                f"memory_limit: {rss_mb:.1f}MB > {limits.rss_limit_mb:.1f}MB",
            )
        sleep(poll_interval_seconds)

    process.join(timeout=1)
    if process.exitcode and process.exitcode != 0:
        stderr_out = getattr(process, "stderr_text", "")
        if stderr_out:
            logger.warning("子进程 stderr (exit %d):\n%s", process.exitcode, stderr_out)
    if result_queue is None:
        return BatchWorkerOutcome(
            False,
            "",
            f"worker_exit: process exited with code {process.exitcode} without a result",
        )
    try:
        return result_queue.get(timeout=1)
    except queue.Empty:
        stderr_out = getattr(process, "stderr_text", "")
        if stderr_out:
            logger.error(
                "Worker %s failed without result. stderr:\n%s", process.pid, stderr_out
            )
        return BatchWorkerOutcome(
            False,
            "",
            f"worker_exit: process exited with code {process.exitcode} without a result",
            stderr_out,
        )


def _new_protocol_file(directory: Path, suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=".uasset-worker-",
        suffix=suffix,
        dir=directory,
        delete=False,
    )
    path = Path(handle.name)
    handle.close()
    return path


def run_isolated_asset(
    request: BatchWorkerRequest,
    limits: ResourceLimits,
    poll_interval_seconds: float,
) -> BatchWorkerOutcome:
    """Run one request in a fresh interpreter and enforce RSS/time limits."""
    protocol_dir = Path(request.output_path).parent
    protocol_dir.mkdir(parents=True, exist_ok=True)
    request_path = _new_protocol_file(protocol_dir, ".request.json")
    result_path = _new_protocol_file(protocol_dir, ".result.json")
    result_path.unlink(missing_ok=True)
    request_path.write_text(
        json.dumps(_request_to_payload(request), ensure_ascii=False),
        encoding="utf-8",
    )
    process = None
    try:
        env = os.environ.copy()
        if request.logging_options and request.logging_options.get("run_id"):
            env["UASSET_READ_RUN_ID"] = request.logging_options["run_id"]
        popen = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uasset_read.batch_worker",
                "--request",
                str(request_path),
                "--result",
                str(result_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
        )
        process = _SubprocessAdapter(popen)
        return _monitor_worker(
            process=process,
            result_queue=_ResultFile(result_path),
            limits=limits,
            poll_interval_seconds=poll_interval_seconds,
        )
    finally:
        if process is not None and process.is_alive():
            _terminate_worker(process)
        if process is not None:
            try:
                _temporary_output_path(request.output_path, process.pid).unlink(
                    missing_ok=True
                )
            except OSError as e:
                logger.debug("清理临时输出文件失败: %s", e)
        request_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)


def _worker_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    request = _request_from_payload(
        json.loads(Path(args.request).read_text(encoding="utf-8"))
    )
    outcome = _asset_worker(request)
    Path(args.result).write_text(
        json.dumps(asdict(outcome), ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_worker_main())
