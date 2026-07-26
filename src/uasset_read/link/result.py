"""Linker parse result -- LinkerParseResult."""
from __future__ import annotations


from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from uasset_read.models.result import ParseResult

if TYPE_CHECKING:
    from uasset_read.link.object_instance import UObjectInstance


@dataclass
class LinkerParseResult(ParseResult):
    """Linker parse result -- full object graph from ImportMap/ExportMap.

    Extends ``ParseResult`` (the single public result contract) with
    linker-specific object-graph fields.  All post-process fields are
    inherited from ``BaseResult`` via ``ParseResult``.
    """

    root_objects: List["UObjectInstance"] = field(default_factory=list)
    all_objects: List["UObjectInstance"] = field(default_factory=list)
