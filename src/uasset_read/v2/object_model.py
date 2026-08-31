"""Object model — v2 types for package objects.

ObjectRecord, ObjectStatus, Region, ObjectRef.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Region:
    offset: int
    size: int


@dataclass(frozen=True)
class ObjectRef:
    """Reference to an import or export by table + index."""

    table: Literal["import", "export"]
    index: int

    def __str__(self) -> str:
        return f"{self.table}:{self.index}"


@dataclass
class ObjectStatus:
    parse: Literal["complete", "partial", "opaque", "failed"] = "complete"
    semantic: Literal["complete", "partial", "unavailable", "not_requested"] = "not_requested"


@dataclass
class CoverageEntry:
    feature: str
    status: Literal["present", "partial", "missing", "unsupported"] = "missing"
    detail: str = ""


@dataclass
class ObjectRecord:
    """Single export or import as a first-class package object."""

    id: str  # "export:0", "import:3"
    table_index: int
    name: str
    class_name: str | None = None
    class_ref: ObjectRef | None = None
    outer_ref: ObjectRef | None = None
    super_ref: ObjectRef | None = None
    template_ref: ObjectRef | None = None
    flags: int = 0
    roles: tuple[str, ...] = ()
    serial_region: Region | None = None
    status: ObjectStatus = field(default_factory=ObjectStatus)
    properties: dict[str, Any] | None = None
    semantic: dict[str, Any] | None = None
    coverage: list[CoverageEntry] = field(default_factory=list)
    diagnostics: list[Any] = field(default_factory=list)


@dataclass
class Relation:
    kind: Literal[
        "outer_of",
        "class_of",
        "generated_class_of",
        "default_object_of",
        "template_of",
        "super_of",
        "depends_on",
        "preload_of",
        "references",
    ]
    from_id: str  # "export:0" or "import:3"
    to_id: str  # "export:1" or "import:5"


@dataclass
class Dependency:
    index: int
    class_name: str
    object_name: str
    package_name: str = ""


@dataclass
class PayloadDescriptor:
    id: str  # "payload:0"
    owner_id: str  # "export:7"
    kind: str  # "texture_mip", "audio", "bulk_data", "other"
    source_region: str  # "main", "uexp", "ubulk", "uptnl", "ucas"
    offset: int
    stored_size: int
    logical_size: int = 0
    compression: str = ""
    status: Literal["available", "external", "missing", "unsupported"] = "unsupported"
    hash: str | None = None


ROLES_ASSET = "asset"
ROLES_GENERATED_CLASS = "generated_class"
ROLES_CDO = "class_default_object"
