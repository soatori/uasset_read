"""User-Defined types semantic JSON domain (#557g)."""

from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.user_defined.extractor import build_user_defined_content

for _class in ("UserDefinedEnum", "UserDefinedStruct"):
    register_extension(
        _class,
        build_user_defined_content,
        domain_format="uasset_read.user_defined_semantic",
        domain_format_version="1.0.0",
    )
