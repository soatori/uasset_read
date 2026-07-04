"""Subprocess-isolated per-asset worker for :func:`uasset_read.core.parse_batch`."""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

from uasset_read.memory_safety import (
    MemoryPolicy,
    ResourceLimits,
    _get_process_rss_mb,
)


@dataclass(frozen=True)
class BatchWorkerRequest:
    file_path: str
    output_path: str
    parse_options: dict[str, Any]


@dataclass(frozen=True)
class BatchWorkerOutcome:
    succeeded: bool
    output_path: str = ""
    error: str = ""


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
    )


def _asset_worker(request: BatchWorkerRequest) -> BatchWorkerOutcome:
    """Parse and atomically publish one asset entirely inside the child."""
    from uasset_read.core import parse_single

    output_path = Path(request.output_path)
    temporary_path = _temporary_output_path(output_path, os.getpid())
    try:
        rendered = parse_single(request.file_path, **request.parse_options)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(rendered, encoding="utf-8")
        os.replace(temporary_path, output_path)
        return BatchWorkerOutcome(True, str(output_path), "")
    except BaseException as exc:
        return BatchWorkerOutcome(
            False,
            "",
            f"{type(exc).__name__}: {exc}",
        )
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError as e:
            logger.debug("清理临时文件失败: %s", e)


class _SubprocessAdapter:
    def __init__(self, process: subprocess.Popen) -> None:
        self._process = process
        self.pid = process.pid
        self._stderr_text: str = ""

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
        return self._stderr_text

    def _drain_stderr(self) -> None:
        """读取并缓存 stderr，防止管道资源泄漏。"""
        if self._process.stderr is not None and self._stderr_text == "":
            try:
                raw = self._process.stderr.read()
                self._stderr_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
            except (OSError, ValueError) as exc:
                logger.debug("读取子进程 stderr 失败: %s", exc)

    def join(self, timeout=None) -> None:
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.debug("子进程 join 超时，继续执行")
        self._drain_stderr()


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
        return BatchWorkerOutcome(
            False,
            "",
            f"worker_exit: process exited with code {process.exitcode} without a result",
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
