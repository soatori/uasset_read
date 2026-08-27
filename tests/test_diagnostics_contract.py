"""Diagnostics contract — failure isolation for property parsing."""

from __future__ import annotations

from pathlib import Path


SAMPLES_DIR = Path(__file__).parent / "samples"
SAMPLE = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")


class TestFailureIsolation:
    """A failed export property parse must not remove later objects."""

    def test_failed_export_does_not_remove_later_objects(self):
        from uasset_read.v2.api import parse_package_document

        # Parse all objects — if one fails, others should still be present
        doc = parse_package_document(SAMPLE, depth="object")
        # All 10 exports should still be in the objects list
        assert len(doc.objects) == 10
        # At least some should have properties
        with_props = [o for o in doc.objects if o.properties is not None]
        assert len(with_props) > 0

    def test_partial_status_on_bad_export_preserves_document(self):
        """If a specific export's properties fail, the document is still valid."""
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object")
        # Document should be fully formed regardless of individual parse failures
        assert doc.package.export_count == 10
        assert len(doc.objects) == 10
        assert len(doc.relations) > 0
        # No critical errors in package-level diagnostics
        critical = [d for d in doc.diagnostics if d.severity == "critical"]
        assert len(critical) == 0

    def test_parse_failure_diagnostic_has_object_id(self):
        """Any EXPORT_PROPERTY_PARSE_FAILED diagnostic references an object."""
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object")
        parse_failures = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_PARSE_FAILED"]
        for diag in parse_failures:
            assert diag.object_id is not None
            assert diag.stage == "properties.tagged"
