"""Blueprint module -- blueprint variable extraction, component transform parsing.

Standalone module (per D-02), shared by property parsing and blueprint graph parsing.
All functions are exported via flat exports (per D-03).
"""

from uasset_read.blueprint.variable_extractor import (
    extract_blueprint_variables,
    extract_blueprint_metadata,
    parse_property_flags_to_labels,
)
from uasset_read.blueprint.transform_parser import (
    extract_component_transforms,
)
from uasset_read.blueprint.component_extractor import (
    extract_components,
)

__all__ = [
    "extract_blueprint_variables",
    "extract_blueprint_metadata",
    "parse_property_flags_to_labels",
    "extract_component_transforms",
    "extract_components",
]
