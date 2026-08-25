"""link/ — UE-style object graph reconstruction.

Provides PackageLinker (FLinkerLoad pattern), UObjectInstance.
Access via: from uasset_read.link import PackageLinker, UObjectInstance
"""

from uasset_read.link.object_instance import UObjectInstance
from uasset_read.link.linker import PackageLinker

__all__ = ["UObjectInstance", "PackageLinker"]
