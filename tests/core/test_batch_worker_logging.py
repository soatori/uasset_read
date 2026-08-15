from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest

from uasset_read.batch_worker import BatchWorkerRequest, run_isolated_asset
from uasset_read.memory_safety import MemoryPolicy
from uasset_read.project_logging import (
    WORKER_LOG_EVENT_PREFIX,
    _reset_logging_state_for_tests,
    configure_project_logging,
    configure_worker_stream_logging,
    forward_worker_log_event,
    shutdown_project_logging,
)


def teardown_function() -> None:
    _reset_logging_state_for_tests()


def test_worker_stream_emits_a_structured_event() -> None:
    stream = io.StringIO()
    handler = configure_worker_stream_logging(
        stream=stream,
        level="debug",
        run_id="batch-run",
        asset="sample.uasset",
    )
    package_logger = logging.getLogger("uasset_read")
    try:
        logging.getLogger("uasset_read.worker_test").warning("recovered offset %d", 12)
    finally:
        package_logger.removeHandler(handler)
        handler.close()

    payload = json.loads(stream.getvalue().removeprefix(WORKER_LOG_EVENT_PREFIX))
    assert payload == {
        "asset": "sample.uasset",
        "level": "WARNING",
        "logger": "uasset_read.worker_test",
        "message": "recovered offset 12",
        "pid": payload["pid"],
        "run_id": "batch-run",
        "stage": "worker",
    }


def test_worker_stream_prevents_project_file_logging(tmp_path) -> None:
    handler = configure_worker_stream_logging(
        stream=io.StringIO(),
        level="debug",
        run_id="batch-run",
        asset="sample.uasset",
    )
    package_logger = logging.getLogger("uasset_read")
    try:
        assert configure_project_logging(log_dir=tmp_path / "worker-logs") is None
    finally:
        package_logger.removeHandler(handler)
        handler.close()

    assert not (tmp_path / "worker-logs").exists()


def test_parent_forwards_worker_event_with_one_formatter_and_worker_context(tmp_path) -> None:
    log_path = configure_project_logging(log_dir=tmp_path, run_id="batch-run")
    assert log_path is not None

    forward_worker_log_event(
        WORKER_LOG_EVENT_PREFIX
        + json.dumps(
            {
                "asset": "sample.uasset",
                "level": "WARNING",
                "logger": "uasset_read.worker_test",
                "message": "recovered offset 12",
                "pid": 4321,
                "run_id": "batch-run",
                "stage": "worker",
            }
        )
    )
    shutdown_project_logging()

    line = log_path.read_text(encoding="utf-8").splitlines()[-1]
    assert "[WARNING] [run=batch-run pid=4321 asset=sample.uasset stage=worker]" in line
    assert line.endswith("uasset_read.worker_test: recovered offset 12")
    assert "worker[" not in line
    assert line.count("[WARNING]") == 1


def test_isolated_worker_writes_only_to_the_parent_log(tmp_path) -> None:
    pytest.skip("Batch worker subprocess requires PYTHONPATH setup")
    sample = Path(__file__).resolve().parents[1] / "samples" / "ALS_AnimBP.uasset"
    log_path = configure_project_logging(log_dir=tmp_path / "logs", run_id="batch-run")
    assert log_path is not None
    request = BatchWorkerRequest(
        file_path=str(sample),
        output_path=str(tmp_path / "output.json"),
        parse_options={"format": "json", "tolerant": True},
        logging_options={"enabled": True, "level": "debug", "run_id": "batch-run"},
    )

    outcome = run_isolated_asset(
        request,
        MemoryPolicy().limits_for_path(sample),
        poll_interval_seconds=0.01,
    )
    shutdown_project_logging()

    assert outcome.succeeded
    assert (tmp_path / "output.json").is_file()
    assert list((tmp_path / "logs").glob("uasset_read*.log*")) == [log_path]
    contents = log_path.read_text(encoding="utf-8")
    assert "asset=ALS_AnimBP.uasset stage=worker" in contents
