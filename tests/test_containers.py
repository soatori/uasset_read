from pathlib import Path

import pytest

from uasset_read.containers import inspect_container

CONTAINERS = Path(__file__).parent / "samples" / "containers"


def test_utoc_lists_packages_without_ucas_body():
    report = inspect_container(CONTAINERS / "MyProject-Windows.utoc")
    assert report.kind == "iostore"
    assert report.entry_count > 0
    # body availability is explicit; missing/chunked payloads must not pretend success
    assert report.capabilities["chunk_bytes"] in {"available", "unavailable"}


def test_missing_key_is_structured_unavailable():
    report = inspect_container(CONTAINERS / "MyProject-Windows.utoc")
    for diag in report.diagnostics:
        assert diag.code
        assert diag.stage.startswith("container")


def test_iostore_wrapper_is_not_treated_as_traditional_pak():
    report = inspect_container(CONTAINERS / "MyProject-Windows.pak")
    assert report.kind == "iostore_wrapper"
    assert report.capabilities["traditional_pak_entries"] == "unavailable"


def test_container_input_is_refused_as_package():
    from uasset_read.exceptions import ParseError
    from uasset_read.package import parse_package_document

    for name in ("MyProject-Windows.utoc", "MyProject-Windows.pak"):
        with pytest.raises(ParseError) as excinfo:
            parse_package_document(CONTAINERS / name)
        assert excinfo.value.code == "CONTAINER_PACKAGE_UNSUPPORTED"
        assert excinfo.value.diagnostics
