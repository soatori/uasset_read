def test_native_field_reflection_payload_is_retained():
    from uasset_read.kismet.native_fields import NativeFieldDeclaration
    from uasset_read.models.byte_ranges import ByteRegion

    field = NativeFieldDeclaration(
        type_name="bool",
        name="bEnabled",
        property_flags=1,
        metadata={"DisplayName": "Enabled"},
        array_dim=1,
        element_size=1,
        rep_index=None,
        rep_notify_func=None,
        replication_condition=None,
        references=[],
        reference_names=[],
        inner_fields=[],
        opaque_metadata=[],
        source_range=ByteRegion(0, 8, "decoded"),
    )
    assert field.property_flags is not None
    assert field.array_dim >= 1
    assert field.element_size >= 0
    assert field.metadata is not None or field.opaque_metadata
    assert field.source_range is not None
