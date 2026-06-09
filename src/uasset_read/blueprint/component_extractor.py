"""组件提取模块 — 从 ExportMap 发现 SCS 组件并提取数值属性。

组件属性递归解析 (D-01, D-02, D-04)。
通过 Outer 层级扫描发现组件对象，提取变换 + 标量属性。

SCS 组件树序列化 (Issue #70)：
从 BPGC 的 SimpleConstructionScript 属性出发，递归解析 USCS_Node 树，
提取完整的组件层次结构、附加关系和类/模板引用。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from uasset_read.serializers.object_resources import (
    ObjectExport,
    ObjectImport,
    PackageIndex,
    resolve_class_name,
)
from uasset_read.blueprint.transform_parser import extract_component_transforms
from uasset_read.models.properties import PropertyValue, StructValue, EnumValue

logger = logging.getLogger(__name__)

_TRANSFORM_NAMES = {"RelativeLocation", "RelativeRotation", "RelativeScale3D"}

_SCALAR_TYPES = {
    "FloatProperty", "IntProperty", "Int64Property",
    "BoolProperty", "ByteProperty", "EnumProperty",
}


def extract_components(
    export_map: List["ObjectExport"],
    import_map: List["ObjectImport"],
) -> List[Dict[str, Any]]:
    """从 ExportMap 发现组件并提取变换 + 标量属性。

    Args:
        export_map: 导出表条目列表
        import_map: 导入表条目列表

    Returns:
        组件字典列表，每个包含 name/class/properties/transforms 键。
    """
    result: List[Dict[str, Any]] = []
    skipped_no_props = 0
    skipped_no_class = 0
    for export in export_map:
        if not export.properties:
            skipped_no_props += 1
            logger.debug("extract_components: skipping export %s — no properties parsed", export.object_name)
            continue

        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name is None or "Component" not in class_name:
            if class_name and "Component" not in class_name:
                skipped_no_class += 1
            continue

        transforms = extract_component_transforms(export.properties, export.object_name)
        scalar_props = _filter_scalar_properties(export.properties)

        result.append({
            "name": export.object_name,
            "class": class_name,
            "properties": scalar_props,
            "transforms": transforms,
        })

    logger.debug(
        "extract_components: found %d components, skipped %d (no props) + %d (no Component class)",
        len(result), skipped_no_props, skipped_no_class,
    )
    return result


# ============================================================================
# SCS 组件树序列化 (Issue #70)
# ============================================================================

# SCS 节点导出必须匹配的类名模式（UE SCS_Node.h）
_SCS_NODE_CLASS_NAMES = {"SCS_Node", "BlueprintGeneratedClass_SCS_Node"}

# SimpleConstructionScript 导出类名模式
_SCS_CLASS_NAMES = {"SimpleConstructionScript", "BlueprintGeneratedClass_SimpleConstructionScript"}


def extract_scs_tree(
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    archive: Any = None,
    summary: Any = None,
    name_map: List[str] = None,
) -> List[Dict[str, Any]]:
    """从 BPGC 的 SimpleConstructionScript 属性提取完整 SCS 组件树。

    遵循 UE 序列化路径：
    1. 找到 BPGC export → SimpleConstructionScript ObjectProperty → SCS export
    2. 解析 SCS export 的 RootNodes/AllNodes 属性（TArray<USCS_Node>）
    3. 对每个 SCS_Node export，递归提取：ComponentClass, ComponentTemplate,
       AttachToName, ParentComponentOrVariableName, ChildNodes, InternalVariableName

    Args:
        export_map: 导出表条目列表（已解析属性）
        import_map: 导入表条目列表
        archive: FArchive 实例（可选，用于解析 SCS 导出属性）
        summary: PackageFileSummary（可选，用于属性解析）
        name_map: 名称表（可选，用于属性解析）

    Returns:
        SCS 节点列表（树形扁平化），每个包含：
        name, class, template, attach_to, parent_component,
        variable_name, children (递归子节点列表)
    """
    # Step 1: 找到 BPGC export
    bpgc_export = _find_bpgc_export(export_map, import_map)
    if bpgc_export is None:
        logger.debug("extract_scs_tree: no BPGC export found")
        return []

    # Step 2: 找到 BPGC 的 SimpleConstructionScript 引用
    scs_ref = _find_scs_export_from_bpgc(bpgc_export, export_map)
    if scs_ref is None:
        logger.debug("extract_scs_tree: no SimpleConstructionScript export found from BPGC '%s'",
                      bpgc_export.object_name)
        return []

    # Step 3: 解析 SCS export 的属性（如果 archive 可用）
    scs_properties = None
    if archive is not None and summary is not None and name_map is not None:
        try:
            from uasset_read.parsers.property_parser import parse_properties_from_export
            scs_properties = parse_properties_from_export(
                scs_ref, archive, summary, name_map, export_map, import_map,
            )
        except Exception as e:
            logger.warning("extract_scs_tree: failed to parse SCS export properties: %s", e)

    # Step 4: 从 SCS export 属性中提取节点引用
    scs_node_exports = _collect_scs_node_exports(scs_ref, scs_properties, export_map, import_map)

    if not scs_node_exports:
        logger.debug("extract_scs_tree: no SCS_Node exports found from SCS '%s'",
                      scs_ref.object_name)
        return []

    # Step 5: 解析每个 SCS_Node 的属性（如果 archive 可用）
    if archive is not None and summary is not None and name_map is not None:
        _parse_scs_node_properties(scs_node_exports, archive, summary, name_map, export_map, import_map)

    # Step 6: 构建树形结构
    result = _build_scs_tree(scs_node_exports, export_map, import_map)

    logger.debug(
        "extract_scs_tree: extracted %d SCS nodes from '%s'",
        len(result), scs_ref.object_name,
    )
    return result


def _find_bpgc_export(
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
) -> Optional[ObjectExport]:
    """找到主 BlueprintGeneratedClass export。"""
    for export in export_map:
        if not export.properties:
            continue
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name and "BlueprintGeneratedClass" in class_name:
            return export
    return None


def _find_scs_property_on_bpgc(bpgc_export: ObjectExport) -> Optional[ObjectExport]:
    """从 BPGC export 的属性中找到 SimpleConstructionScript 引用。

    SimpleConstructionScript 是一个 ObjectProperty，
    其值（解析后）指向一个 USimpleConstructionScript 导出。
    """
    for prop in bpgc_export.properties:
        if prop.name == "SimpleConstructionScript":
            value = prop.value
            if isinstance(value, dict):
                # linker 解析后的格式
                if value.get("type") == "export":
                    return None  # 需要找到 export 对象
            elif isinstance(value, int):
                # PackageIndex raw 值
                pkg_idx = PackageIndex(value)
                if pkg_idx.is_export:
                    return None  # 需要 export_map 来查找
    return None


def _find_scs_export_from_bpgc(
    bpgc_export: ObjectExport,
    export_map: List[ObjectExport],
) -> Optional[ObjectExport]:
    """通过 outer_index 关系找到 BPGC 的 SCS 子导出。

    UE 中 USimpleConstructionScript 是 BPGC 的子对象，
    其 outer_index 指向 BPGC export。
    同时验证其类名匹配 SimpleConstructionScript。
    """
    # 找到 BPGC 在 export_map 中的索引
    bpgc_idx = None
    for i, exp in enumerate(export_map):
        if exp is bpgc_export:
            bpgc_idx = i
            break
    if bpgc_idx is None:
        return None

    for export in export_map:
        if export is bpgc_export:
            continue
        # outer 指向 BPGC
        if export.outer_index.is_export:
            outer_idx = export.outer_index.to_export_index()
            if outer_idx == bpgc_idx:
                # 验证类名是否为 SimpleConstructionScript
                object_name = export.object_name
                if "SimpleConstructionScript" in object_name:
                    return export
    return None


def _collect_scs_node_exports(
    scs_export: ObjectExport,
    scs_properties: Optional[List[PropertyValue]],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
) -> List[ObjectExport]:
    """从 SCS export 的 RootNodes/AllNodes 属性中收集所有 SCS_Node 导出。"""
    node_exports: List[ObjectExport] = []
    seen_indices: set = set()

    # 方法 1：从解析后的属性中提取引用
    if scs_properties:
        for prop in scs_properties:
            if prop.name in ("RootNodes", "AllNodes"):
                _collect_node_refs_from_property(prop.value, export_map, node_exports, seen_indices)

    # 方法 2：通过 outer 关系收集（回退）
    if not node_exports:
        # 找到 SCS export 在 export_map 中的索引
        scs_idx = None
        for i, exp in enumerate(export_map):
            if exp is scs_export:
                scs_idx = i
                break
        if scs_idx is not None:
            for export in export_map:
                if export is scs_export:
                    continue
                if export.outer_index.is_export:
                    outer_idx = export.outer_index.to_export_index()
                    if outer_idx == scs_idx:
                        node_name = export.object_name
                        if "SCS_Node" in node_name or "SCSNode" in node_name:
                            if id(export) not in seen_indices:
                                node_exports.append(export)
                                seen_indices.add(id(export))

    return node_exports


def _collect_node_refs_from_property(
    value: Any,
    export_map: List[ObjectExport],
    node_exports: List[ObjectExport],
    seen_indices: set,
) -> None:
    """从属性值中递归收集 SCS_Node 导出引用。"""
    if isinstance(value, list):
        for item in value:
            _collect_node_refs_from_property(item, export_map, node_exports, seen_indices)
    elif isinstance(value, int):
        pkg_idx = PackageIndex(value)
        if pkg_idx.is_export:
            idx = pkg_idx.to_export_index()
            if 0 <= idx < len(export_map):
                export = export_map[idx]
                if id(export) not in seen_indices:
                    node_exports.append(export)
                    seen_indices.add(id(export))
    elif isinstance(value, dict):
        # linker 解析后的格式
        if value.get("type") == "export":
            # 通过 object_name 查找
            obj_name = value.get("object_name", "")
            for export in export_map:
                if export.object_name == obj_name and id(export) not in seen_indices:
                    node_exports.append(export)
                    seen_indices.add(id(export))


def _parse_scs_node_properties(
    node_exports: List[ObjectExport],
    archive: Any,
    summary: Any,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
) -> None:
    """为尚未解析属性的 SCS_Node 导出解析属性。"""
    from uasset_read.parsers.property_parser import parse_properties_from_export

    for export in node_exports:
        if export.properties:
            continue  # 已有属性，跳过
        if export.serial_size <= 0:
            continue
        try:
            export.properties = parse_properties_from_export(
                export, archive, summary, name_map, export_map, import_map,
            )
        except Exception as e:
            logger.debug("extract_scs_tree: failed to parse SCS_Node '%s': %s",
                         export.object_name, e)


def _build_scs_tree(
    scs_node_exports: List[ObjectExport],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
) -> List[Dict[str, Any]]:
    """从 SCS_Node 导出列表构建树形结构。

    使用 ParentComponentOrVariableName 和 ChildNodes 属性
    建立父子关系。没有父节点的节点作为根节点。
    """
    # 为每个节点构建信息字典
    node_info: Dict[int, Dict[str, Any]] = {}  # export_index -> info

    for i, export in enumerate(scs_node_exports):
        info = _extract_scs_node_info(export, export_map, import_map)
        node_info[i] = info

    # 建立父子关系
    # 通过 ParentComponentOrVariableName 查找父节点
    children_map: Dict[int, List[int]] = {}  # parent_index -> [child_indices]

    for i, export in enumerate(scs_node_exports):
        info = node_info[i]
        parent_name = info.get("parent_component", "")
        if parent_name:
            # 查找父节点
            for j, other_export in enumerate(scs_node_exports):
                if i == j:
                    continue
                other_info = node_info[j]
                if other_info.get("variable_name") == parent_name:
                    if j not in children_map:
                        children_map[j] = []
                    children_map[j].append(i)
                    break

    # 也通过 ChildNodes 属性建立关系
    for i, export in enumerate(scs_node_exports):
        if export.properties:
            for prop in export.properties:
                if prop.name == "ChildNodes":
                    child_refs = prop.value if isinstance(prop.value, list) else []
                    for ref in child_refs:
                        child_idx = _resolve_export_index(ref, scs_node_exports, export_map)
                        if child_idx is not None and child_idx != i:
                            if i not in children_map:
                                children_map[i] = []
                            if child_idx not in children_map[i]:
                                children_map[i].append(child_idx)

    # 找出根节点（没有父节点的节点）
    all_indices = set(range(len(scs_node_exports)))
    child_indices = set()
    for children in children_map.values():
        child_indices.update(children)
    root_indices = sorted(all_indices - child_indices)

    # 递归构建结果
    result: List[Dict[str, Any]] = []
    visited: set = set()

    def _build_node(idx: int) -> Dict[str, Any]:
        visited.add(idx)
        info = node_info[idx]
        children = []
        for child_idx in children_map.get(idx, []):
            if child_idx not in visited:
                children.append(_build_node(child_idx))
        info["children"] = children
        return info

    for root_idx in root_indices:
        result.append(_build_node(root_idx))

    # 处理循环引用或孤立节点
    for i in range(len(scs_node_exports)):
        if i not in visited:
            result.append(_build_node(i))

    return result


def _extract_scs_node_info(
    export: ObjectExport,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
) -> Dict[str, Any]:
    """从 SCS_Node 导出中提取节点信息。

    完整提取 UE SCS_Node.h 定义的所有关键字段：
    - ComponentClass / ComponentTemplate (组件类/模板)
    - AttachToName / ParentComponentOrVariableName (父子关系)
    - InternalVariableName (内部变量名)
    - VariableGuid (变量 GUID)
    - MetaDataArray (元数据数组)
    - CategoryName (分类名称，editor only)
    - bIsParentComponentNative / ParentComponentOwnerClassName (父组件原生标志)
    """
    info: Dict[str, Any] = {
        "name": export.object_name,
        "class": "",
        "class_full": "",
        "template": "",
        "attach_to": "",
        "variable_name": "",
        "variable_guid": "",  # Issue #70: 新增 VariableGuid 字段
        "parent_component": "",
        "parent_owner_class": "",
        "is_parent_native": False,
        "category_name": "",  # Issue #70: 新增 CategoryName 字段
        "metadata": {},  # Issue #70: 新增 MetaDataArray 解析结果
        "children": [],
    }

    if not export.properties:
        return info

    for prop in export.properties:
        if prop.name == "ComponentClass":
            class_ref = _resolve_object_property(prop.value, export_map, import_map)
            if class_ref:
                info["class"] = class_ref.get("object_name", "")
                info["class_full"] = class_ref.get("full_name", class_ref.get("object_name", ""))

        elif prop.name == "ComponentTemplate":
            template_ref = _resolve_object_property(prop.value, export_map, import_map)
            if template_ref:
                info["template"] = template_ref.get("object_name", "")

        elif prop.name == "AttachToName":
            if isinstance(prop.value, str):
                info["attach_to"] = prop.value

        elif prop.name == "ParentComponentOrVariableName":
            if isinstance(prop.value, str):
                info["parent_component"] = prop.value

        elif prop.name == "ParentComponentOwnerClassName":
            if isinstance(prop.value, str):
                info["parent_owner_class"] = prop.value

        elif prop.name == "bIsParentComponentNative":
            if isinstance(prop.value, bool):
                info["is_parent_native"] = prop.value

        elif prop.name == "InternalVariableName":
            if isinstance(prop.value, str):
                info["variable_name"] = prop.value

        # Issue #70: 新增 VariableGuid 字段解析
        elif prop.name == "VariableGuid":
            # FGuid 类型，可能是 StructValue 或字符串
            guid_value = _extract_guid(prop.value)
            if guid_value:
                info["variable_guid"] = guid_value

        # Issue #70: 新增 CategoryName 字段解析 (WITH_EDITORONLY_DATA)
        elif prop.name == "CategoryName":
            # FText 类型，需要提取 DisplayBase 或直接取字符串
            category = _extract_text(prop.value)
            if category:
                info["category_name"] = category

        # Issue #70: 新增 MetaDataArray 字段解析
        elif prop.name == "MetaDataArray":
            # TArray<FBPVariableMetaDataEntry> 类型
            metadata = _extract_metadata_array(prop.value)
            if metadata:
                info["metadata"] = metadata

    return info


def _extract_guid(value: Any) -> str:
    """从属性值中提取 GUID 字符串。

    FGuid 在序列化中可能是：
    - StructValue (包含 A/B/C/D 字段)
    - 字典格式
    - 已经是字符串格式
    """
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        # linker 解析后的格式，可能有 'value' 或 'guid' 键
        return value.get("value", value.get("guid", ""))

    # StructValue 或其他对象
    if hasattr(value, "fields"):
        # StructValue 格式：{A: int, B: int, C: int, D: int}
        fields = getattr(value, "fields", {})
        try:
            a = fields.get("A", 0)
            b = fields.get("B", 0)
            c = fields.get("C", 0)
            d = fields.get("D", 0)
            # FGuid 是 16 字节，序列化为 32 位 hex
            return f"{a:08X}{b:08X}{c:08X}{d:08X}".lower()
        except (AttributeError, TypeError):
            pass

    return ""


def _extract_text(value: Any) -> str:
    """从 FText 属性值中提取文本字符串。

    FText 在序列化中可能是：
    - StructValue (包含 Flags, HistoryType, Namespace, Key, SourceString)
    - 字典格式
    - 直接字符串
    """
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        # linker 解析后的格式
        return value.get("SourceString", value.get("value", ""))

    # StructValue 格式
    if hasattr(value, "fields"):
        fields = getattr(value, "fields", {})
        return fields.get("SourceString", "")

    return ""


def _extract_metadata_array(value: Any) -> Dict[str, str]:
    """从 MetaDataArray 属性值中提取元数据字典。

    TArray<FBPVariableMetaDataEntry> 每个元素包含：
    - MetaDataEntryName (FName)
    - MetaDataEntryValue (FString)
    """
    result: Dict[str, str] = {}

    if not isinstance(value, list):
        return result

    for entry in value:
        if isinstance(entry, dict):
            # linker 解析后的格式
            name = entry.get("MetaDataEntryName", entry.get("name", ""))
            val = entry.get("MetaDataEntryValue", entry.get("value", ""))
            if name and val:
                result[name] = val
        elif hasattr(entry, "fields"):
            # StructValue 格式
            fields = getattr(entry, "fields", {})
            name = fields.get("MetaDataEntryName", "")
            val = fields.get("MetaDataEntryValue", "")
            if name and val:
                result[name] = val

    return result


def _resolve_object_property(
    value: Any,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
) -> Optional[Dict[str, str]]:
    """解析 ObjectProperty 值为引用信息。"""
    if isinstance(value, dict):
        # linker 解析后的格式
        return {
            "object_name": value.get("object_name", ""),
            "object_class": value.get("object_class", ""),
            "full_name": value.get("full_name", ""),
            "type": value.get("type", ""),
        }
    elif isinstance(value, int):
        pkg_idx = PackageIndex(value)
        if pkg_idx.is_null:
            return None
        if pkg_idx.is_import:
            idx = pkg_idx.to_import_index()
            if 0 <= idx < len(import_map):
                imp = import_map[idx]
                return {
                    "object_name": imp.object_name,
                    "object_class": imp.class_name,
                    "full_name": f"{imp.class_package}.{imp.object_name}" if imp.class_package else imp.object_name,
                    "type": "import",
                }
        elif pkg_idx.is_export:
            idx = pkg_idx.to_export_index()
            if 0 <= idx < len(export_map):
                exp = export_map[idx]
                class_name = resolve_class_name(exp.class_index, import_map, export_map) or ""
                return {
                    "object_name": exp.object_name,
                    "object_class": class_name,
                    "full_name": exp.object_name,
                    "type": "export",
                }
    return None


def _resolve_export_index(
    ref: Any,
    node_exports: List[ObjectExport],
    export_map: List[ObjectExport],
) -> Optional[int]:
    """将属性引用解析为 node_exports 列表中的索引。"""
    if isinstance(ref, int):
        pkg_idx = PackageIndex(ref)
        if pkg_idx.is_export:
            target_idx = pkg_idx.to_export_index()
            for i, node_exp in enumerate(node_exports):
                # 找到对应的 export_map 中的 export
                for j, exp in enumerate(export_map):
                    if exp is node_exp and j == target_idx:
                        return i
    return None


# ============================================================================
# 标量属性过滤 (原有功能)
# ============================================================================

def _filter_scalar_properties(properties: List[PropertyValue]) -> Dict[str, Any]:
    """从属性列表中过滤并提取标量属性（D-02）。

    包含 Float/Int/Int64/Bool/Byte/Enum 类型 + 简单 StructProperty（一层展开）。
    排除变换相关的 StructProperty（已由 extract_component_transforms 处理）。
    """
    result: Dict[str, Any] = {}
    for prop in properties:
        if prop.type in _SCALAR_TYPES:
            result[prop.name] = _serialize_scalar_value(prop.value)
        elif prop.type == "StructProperty" and prop.value and prop.name not in _TRANSFORM_NAMES:
            if isinstance(prop.value, StructValue):
                result[prop.name] = {
                    k: _serialize_scalar_value(v)
                    for k, v in prop.value.fields.items()
                }
    return result


def _serialize_scalar_value(value: Any) -> Any:
    """将属性值序列化为 JSON 兼容格式。"""
    if isinstance(value, EnumValue):
        return value.value_name
    if isinstance(value, StructValue):
        return {k: _serialize_scalar_value(v) for k, v in value.fields.items()}
    if isinstance(value, list):
        return [_serialize_scalar_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _serialize_scalar_value(v) for k, v in value.items()}
    return value
