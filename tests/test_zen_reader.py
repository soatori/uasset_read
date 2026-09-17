from pathlib import Path

from uasset_read.containers import inspect_container
from uasset_read.parsers.zen_reader import ZenPackageReader

CONTAINERS = Path(__file__).parent / "samples" / "containers"


def test_zen_reader_reports_unavailable_without_chunk_bytes():
    report = inspect_container(CONTAINERS / "MyProject-Windows.utoc")
    result = ZenPackageReader().read_from_container(
        report,
        package_id="<fixture-package-not-provided>",
        depth="package",
    )
    assert result.document is None
    assert result.status == "unavailable"
    assert result.reason in {"chunk_bytes_unavailable", "zen_package_fixture_unavailable"}
    assert result.diagnostics
    assert all(d.stage.startswith("zen") or d.stage.startswith("container") for d in result.diagnostics)
