"""Property contract — normalize_property_bag, object-depth selection."""

from __future__ import annotations

import json
from pathlib import Path


SAMPLES_DIR = Path(__file__).parent.parent / "samples"
SAMPLE = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")

# Exports with known data issues — serial region extends beyond file size
KNOWN_CORRUPT_EXPORTS = {"export:6"}  # K2Node_Event_1


class TestNormalizePropertyBag:
    """Tests for normalize_property_bag."""

    def test_empty_list_returns_empty_dict(self):
        from uasset_read.v2.properties import normalize_property_bag

        assert normalize_property_bag([]) == {}

    def test_unknown_property_is_descriptor_not_blob(self):
        from uasset_read.models.fallback import FallbackReason, PropertyFallback
        from uasset_read.v2.properties import normalize_property_bag

        prop = PropertyFallback(
            name="Mystery",
            type="UnknownProperty",
            size=4,
            raw_bytes=b"\x01\x02\x03\x04",
            reason=FallbackReason.UNSUPPORTED_TYPE,
        )
        bag = normalize_property_bag([prop])
        assert bag["Mystery"]["kind"] == "opaque"
        assert bag["Mystery"]["size"] == 4
        assert "raw_bytes" not in bag["Mystery"]
        # Must be JSON-serializable
        json.dumps(bag)

    def test_known_property_preserves_value(self):
        from uasset_read.models.properties import PropertyValue
        from uasset_read.v2.properties import normalize_property_bag

        bag = normalize_property_bag([PropertyValue(name="Health", type="FloatProperty", value=100.0)])
        assert bag["Health"]["kind"] == "value"
        assert bag["Health"]["value"] == 100.0

    def test_struct_property_normalizes(self):
        from uasset_read.models.properties import PropertyValue, StructValue
        from uasset_read.v2.properties import normalize_property_bag

        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.0, "Y": 2.0, "Z": 3.0},
        )
        prop = PropertyValue(name="Location", type="StructProperty", value=sv)
        bag = normalize_property_bag([prop])
        assert bag["Location"]["kind"] == "struct"
        assert bag["Location"]["struct_type"] == "Vector"
        assert bag["Location"]["fields"]["X"] == 1.0

    def test_bytes_value_serializes(self):
        from uasset_read.models.properties import PropertyValue
        from uasset_read.v2.properties import normalize_property_bag

        bag = normalize_property_bag([PropertyValue(name="Data", type="BlobProperty", value=b"\x00\x01")])
        assert bag["Data"]["kind"] == "value"
        assert bag["Data"]["value"]["kind"] == "bytes"
        assert bag["Data"]["value"]["length"] == 2


class TestObjectDepthSelection:
    """Tests for depth='object' property parsing selection."""

    def test_object_depth_parses_only_requested_export(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object", object_ids=["export:1"])
        parsed = [obj.id for obj in doc.objects if obj.properties is not None]
        assert parsed == ["export:1"]
        assert len(doc.objects) == doc.package.export_count

    def test_package_depth_has_no_properties(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="package")
        for obj in doc.objects:
            assert obj.properties is None, f"{obj.id} should have no properties at package depth"

    def test_object_depth_all_when_no_ids(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object")
        for obj in doc.objects:
            assert obj.properties is not None, f"{obj.id} should have properties at object depth"
            if obj.serial_region and obj.serial_region.size > 0:
                if obj.id in KNOWN_CORRUPT_EXPORTS:
                    continue

    def test_properties_are_json_serializable(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object", object_ids=["export:0"])
        obj = doc.objects[0]
        assert obj.properties is not None
        json.dumps(obj.properties)


class TestHealthySamplePropertyGates:
    """Healthy legacy samples must produce real properties, not empty failure fallbacks."""

    def test_requested_export_has_nonempty_properties(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object", object_ids=["export:1"])
        obj = doc.objects[1]
        assert obj.properties is not None
        assert len(obj.properties) > 0, "export:1 has an empty property bag — likely a silent parse failure"

    def test_healthy_sample_has_no_property_parse_failures(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object")
        failures = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_PARSE_FAILED"]
        # Exclude exports with known data issues
        real_failures = [f for f in failures if f.object_id not in KNOWN_CORRUPT_EXPORTS]
        assert real_failures == [], f"healthy sample produced {len(real_failures)} unexpected property parse failures"

    def test_all_exports_with_serial_region_get_properties(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object")
        for obj in doc.objects:
            if obj.serial_region and obj.serial_region.size > 0:
                if obj.id in KNOWN_CORRUPT_EXPORTS:
                    continue
                assert obj.properties is not None, f"{obj.id} has no property bag"


class TestPropertyBoundEnforcement:
    def test_parse_past_serial_end_is_flagged_not_silent(self, monkeypatch):
        import uasset_read.parsers.property_parser as pp
        from uasset_read.v2.api import parse_package_document

        def fake_overrun(**kwargs):
            export = kwargs["export"]
            kwargs["archive"].seek(export.serial_offset + export.serial_size + 8)
            return []

        monkeypatch.setattr(pp, "parse_properties_from_export", fake_overrun)
        doc = parse_package_document(SAMPLE, depth="object")
        overrun = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_BOUNDS_EXCEEDED"]
        assert overrun, "property parse exceeded the serial region with no diagnostic"
        assert all(d.object_id and d.stage == "properties.tagged" for d in overrun)

    def test_v2_path_emits_no_handler_warnings(self, capfd, caplog):
        # capfd alone cannot catch the leak under pytest: the logging plugin
        # installs a root handler, which suppresses logging.lastResort. Assert
        # on captured WARNING records too — the real contract is "no warning
        # logs on the v2 parse path".
        import logging

        from uasset_read.v2.api import parse_package_document

        with caplog.at_level(logging.WARNING):
            parse_package_document(
                SAMPLES_DIR / "NM_BPSystemEvent.uasset", depth="object"
            )
        captured = capfd.readouterr()
        assert captured.err == "", f"v2 parse leaked stderr: {captured.err[:200]}"
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings == [], (
            f"v2 parse emitted warning logs: {[r.getMessage()[:120] for r in warnings]}"
        )
