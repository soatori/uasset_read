"""Regression coverage for #514 InheritableComponentHandler exports."""

from __future__ import annotations

from uasset_read.archive import ByteArchive
from uasset_read.models.properties import PropertyTag
from uasset_read.parsers import property_types
from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    get_serialization_strategy,
)
from uasset_read.parsers.class_specific_skip import should_skip_export_class_prefix
from uasset_read.parsers.property_types import parse_struct_property


def test_inheritable_component_handler_uses_generic_tagged_properties() -> None:
    """Records is a tagged UPROPERTY, not an unsupported native payload."""
    assert not should_skip_export_class_prefix("InheritableComponentHandler")
    assert (
        get_serialization_strategy("InheritableComponentHandler")
        is SerializationStrategy.TAGGED_PROPERTIES_ONLY
    )


def test_component_override_record_zero_size_uses_tagged_fields(monkeypatch) -> None:
    """Array inner records still carry their own PropertyTag sequence."""
    tags = iter((
        PropertyTag(name="ComponentClass", type="ObjectProperty", size=4),
        PropertyTag(name="None", type="", size=0),
    ))
    monkeypatch.setattr(
        property_types,
        "_get_read_property_tag",
        lambda: lambda *_args: next(tags),
    )
    monkeypatch.setattr(
        property_types,
        "_get_parse_property_value",
        lambda: lambda *_args: -22,
    )

    value = parse_struct_property(
        PropertyTag(
            name="Records[0]",
            type="StructProperty",
            size=0,
            struct_type="ComponentOverrideRecord",
        ),
        ByteArchive(b"\0" * 4),
        [],
        [],
    )

    assert value.parse_status == "success"
    assert value.fields == {"ComponentClass": -22}
