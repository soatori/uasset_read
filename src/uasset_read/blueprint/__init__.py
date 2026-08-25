"""Blueprint module -- blueprint variable extraction, component transform parsing.

Standalone module (per D-02), shared by property parsing and blueprint graph parsing.
All functions are exported via flat exports (per D-03).
"""

from uasset_read.blueprint.variable_extractor import (
    extract_blueprint_variables,
    extract_blueprint_metadata,
    parse_property_flags_to_labels,
    read_blueprint_variable,
)
from uasset_read.blueprint.transform_parser import (
    extract_component_transforms,
    parse_vector_value,
    parse_rotator_value,
    parse_scale_value,
    format_transform_value,
)
from uasset_read.blueprint.component_extractor import (
    extract_components,
)

__all__ = [
    "extract_blueprint_variables",
    "extract_blueprint_metadata",
    "parse_property_flags_to_labels",
    "read_blueprint_variable",
    "extract_component_transforms",
    "parse_vector_value",
    "parse_rotator_value",
    "parse_scale_value",
    "format_transform_value",
    "extract_components",
]
