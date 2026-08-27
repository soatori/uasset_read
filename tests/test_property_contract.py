"""Property contract — normalize_property_bag, object-depth selection."""

from __future__ import annotations

import json
from pathlib import Path


SAMPLES_DIR = Path(__file__).parent / "samples"
SAMPLE = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")


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

        bag = normalize_property_bag(
            [PropertyValue(name="Health", type="FloatProperty", value=100.0)]
        )
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

        bag = normalize_property_bag(
            [PropertyValue(name="Data", type="BlobProperty", value=b"\x00\x01")]
        )
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

    def test_properties_are_json_serializable(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object", object_ids=["export:0"])
        obj = doc.objects[0]
        assert obj.properties is not None
        json.dumps(obj.properties)
