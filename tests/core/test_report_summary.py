"""Tests for ReportSummary class."""
import pytest


def test_report_summary_generation():
    """Test basic summary generation from parse results."""
    from uasset_read.report_summary import ReportSummary

    results = [
        {"status": "success", "exports": 10, "warnings": 0},
        {"status": "partial", "exports": 5, "warnings": 2, "parse_status": "opaque"},
        {"status": "partial", "exports": 3, "warnings": 1, "parse_status": "partial_metadata"},
        {"status": "failed", "exports": 0, "warnings": 0, "error": "Negative compressed_chunks count"},
    ]

    summary = ReportSummary.from_results(results)

    assert summary.total == 4
    assert summary.success == 1
    assert summary.partial == 2
    assert summary.failed == 1
    assert "opaque" in summary.partial_reasons
    assert summary.most_common_error == "Negative compressed_chunks count"


def test_report_summary_text_output():
    """Test text output generation."""
    from uasset_read.report_summary import ReportSummary

    results = [
        {"status": "success", "exports": 10, "warnings": 0},
        {"status": "partial", "exports": 5, "warnings": 2, "parse_status": "opaque"},
    ]

    summary = ReportSummary.from_results(results)
    text = summary.to_text()

    assert "=== Parse Summary ===" in text
    assert "Total files: 2" in text
    assert "Success: 1" in text
    assert "Partial: 1" in text
    assert "Failed: 0" in text
    assert "Total exports: 15" in text
    assert "Avg exports per file: 7.5" in text
    assert "Total warnings: 2" in text


def test_report_summary_empty_results():
    """Test summary generation with empty results list."""
    from uasset_read.report_summary import ReportSummary

    summary = ReportSummary.from_results([])

    assert summary.total == 0
    assert summary.success == 0
    assert summary.partial == 0
    assert summary.failed == 0
    assert summary.avg_exports_per_file == 0.0
    assert summary.most_common_error == ""
    assert summary.most_common_partial_reason == ""


def test_report_summary_statistics():
    """Test statistics calculation."""
    from uasset_read.report_summary import ReportSummary

    results = [
        {"status": "success", "exports": 20, "warnings": 5},
        {"status": "success", "exports": 10, "warnings": 3},
        {"status": "partial", "exports": 5, "warnings": 2, "parse_status": "opaque"},
    ]

    summary = ReportSummary.from_results(results)

    assert summary.total_exports == 35
    assert summary.total_warnings == 10
    assert summary.avg_exports_per_file == pytest.approx(11.666666666666666)
