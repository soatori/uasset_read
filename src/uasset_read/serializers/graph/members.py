"""FMemberReference 序列化器 — 成员引用结构读取。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.models.core import FMemberReference
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.serializers.graph._common import _rcn, _read_guid


def read_fmember_reference(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> FMemberReference:
    """读取 FMemberReference（MemberReference.h L74-95）。"""
    member_parent_index = archive.read_i32()
    member_parent: Optional[str] = None
    if member_parent_index != 0:
        member_parent = _rcn(
            PackageIndex(member_parent_index), import_map, export_map, linker
        )

    member_scope = archive.read_fstring()
    member_name = archive.read_name(name_map)
    member_guid = _read_guid(archive, uppercase=False)
    b_self_context = archive.read_bool()
    _b_was_deprecated = archive.read_bool()

    return FMemberReference(
        member_parent=member_parent,
        member_name=member_name,
        member_guid=member_guid,
        b_self_context=b_self_context,
    )
