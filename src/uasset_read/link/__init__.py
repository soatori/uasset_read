"""link/ — UE-style object graph reconstruction.

Provides PackageLinker (FLinkerLoad pattern), UObjectInstance, and LinkerParseResult.
Access via: from uasset_read.link import PackageLinker, UObjectInstance, LinkerParseResult
"""

from uasset_read.link.object_instance import UObjectInstance
from uasset_read.link.linker import PackageLinker
from uasset_read.link.result import LinkerParseResult

__all__ = ["UObjectInstance", "PackageLinker", "LinkerParseResult"]
