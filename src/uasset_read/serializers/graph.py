"""蓝图图共享辅助函数与 UEdGraph 读取。

Pin 和 Node 相关函数已拆分到 graph_pin.py 和 graph_node.py。
本模块保留共享辅助函数、诊断追踪和 UEdGraph 容器读取。
"""
from __future__ import annotations

import logging
import os
import struct
import threading
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    MAX_NODES_PER_GRAPH, MAX_SUBGRAPHS, MAX_SAFE_COUNT, format_guid_bytes,
)
from uasset_read.exceptions import ParseError
from uasset_read.serializers.object_resources import (
    resolve_class_name, resolve_class_name_with_linker,
    get_asset_class, get_asset_class_with_linker,
)
from uasset_read.serializers.property_tags import read_tag_value_bounded
from uasset_read.models.core import UEdGraph, UEdGraphNode

logger = logging.getLogger(__name__)

_thread_local = threading.local()


# ============================================================================
# 共享辅助函数
# ============================================================================

def _read_guid(archive: FArchive, uppercase: bool = True) -> str:
    data = archive.read_bytes(16)
    if len(data) != 16:
        raise ParseError(f"FGuid requires 16 bytes, got {len(data)}")
    return format_guid_bytes(data, uppercase=uppercase)


def _get_thread_local():
    """返回当前线程的隔离诊断状态，避免全局可变状态竞态。"""
    if not hasattr(_thread_local, 'linkedto_failure_seen'):
        _thread_local.linkedto_failure_seen: set[tuple[int, str, str]] = set()
        _thread_local.pin_trace_events: List[Dict[str, Any]] = []
        _thread_local.pin_recovery_events: List[Dict[str, Any]] = []
    return _thread_local


def _rcn(idx, im, em, lk):
    """Resolve class name - linker version if available."""
    return (resolve_class_name_with_linker(idx, lk) if lk else resolve_class_name(idx, im, em))


def _gac(exp, im, em, lk):
    """Get asset class - linker version if available."""
    return (get_asset_class_with_linker(exp, lk) if lk else get_asset_class(exp, im, em))


# ============================================================================
# 诊断追踪
# ============================================================================

def _pin_trace_enabled(explicit: bool = False) -> bool:
    return explicit or os.environ.get("UASSET_READ_PIN_TRACE", "").lower() in {
        "1", "true", "yes", "on",
    }


def _record_pin_recovery(event: Dict[str, Any]) -> None:
    _get_thread_local().pin_recovery_events.append(dict(event))


def _trace_fields_append(
    trace_fields: Dict[str, Any],
    name: str, start: int, end: int, value_preview: str = "",
    is_exception: bool = False, is_fallback: bool = False,
) -> None:
    """记录单个字段的追踪信息。"""
    trace_fields.setdefault("fields", []).append({
        "name": name,
        "start": start,
        "end": end,
        "consumed": end - start,
        "value": value_preview[:50],
        "exception": is_exception,
        "fallback": is_fallback,
    })


# ============================================================================
# PropertyTag helper functions
# ============================================================================

def _read_tag_bool(archive: FArchive, tag) -> bool:
    """读取 PropertyTag 中的 bool 值。

    统一处理 inline bool 与 value body 两种形态：
    - tag.size > 0: 从 value body 读取 i32 (UE5 bool serialization)
    - tag.size == 0: 使用 tag.bool_val (inline bool)

    Args:
        archive: FArchive 实例
        tag: PropertyTag 实例

    Returns:
        bool 值
    """
    def _reader() -> bool:
        if tag.size > 0:
            return archive.read_i32() != 0
        return tag.bool_val != 0

    return read_tag_value_bounded(archive, tag, _reader)


def _read_tag_i32(archive: FArchive, tag) -> int:
    """读取 PropertyTag 中的 int32 值并确保 seek 到 value_end_offset。

    标准化 int property 读取流程。

    Args:
        archive: FArchive 实例
        tag: PropertyTag 实例

    Returns:
        int32 值
    """
    return read_tag_value_bounded(archive, tag, archive.read_i32)


def _read_tag_fname(archive: FArchive, tag, name_map: List[str]) -> str:
    """读取 PropertyTag 中的 FName 值并确保 seek 到 value_end_offset。

    标准化 FName property 读取流程。

    Args:
        archive: FArchive 实例
        tag: PropertyTag 实例
        name_map: 名称映射列表

    Returns:
        FName 字符串
    """
    return read_tag_value_bounded(archive, tag, lambda: archive.read_name(name_map))


# ============================================================================
# FText 读取（UE5 多 history_type 支持）
# ============================================================================

def _read_fstring_safe(archive: FArchive, max_length: int = MAX_SAFE_COUNT) -> str:
    """读取 FString，对异常长度进行容错处理。

    参考 UE C++ FArchive& operator<<(FString&) 实现

    FString 序列化格式 (UE C++ Archive.h L209-230):
    - length == 0: 空字符串（无数据区）
    - length == -1: 空字符串特殊标记（UE 内部优化，无数据区）
    - length > 0: ANSI 字符串，读取 length bytes
    - length < -1: UTF-16 字符串，读取 (-length * 2) bytes

    修复 length == -1 边界条件（SubPin PinToolTip 常见）。
    """
    length = archive.read_i32()
    if length == 0 or length == -1:
        # length=-1 是 UE 空字符串标记，不读取任何数据
        return ""
    if abs(length) > max_length:
        # 长度异常，回退并返回空字符串
        if archive.tell() >= 4:
            archive.seek(archive.tell() - 4)
        return ""
    if length < -1:
        utf16_len = -length * 2
        if utf16_len > max_length * 2:
            if archive.tell() >= 4:
                archive.seek(archive.tell() - 4)
            return ""
        data = archive.read(utf16_len)
        return data.decode('utf-16-le', errors='replace').rstrip('\x00')
    data = archive.read(length)
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def _read_ftext_fstring(archive: FArchive) -> str:
    """读取 FText 内部 FString。

    与 _read_fstring_safe 不同，此函数在长度异常时直接抛错，由上层决定
    是否整体回退整个 FText。这样可以避免"少读一部分 body 但继续向后走"
    的隐性错位。
    """
    length = archive.read_i32()
    if length == 0 or length == -1:
        return ""
    if abs(length) > MAX_SAFE_COUNT:
        raise ParseError(f"Invalid FText FString length: {length}")
    if length < -1:
        data = archive.read(-length * 2)
        return data.decode('utf-16-le', errors='replace').rstrip('\x00')
    data = archive.read(length)
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def _read_ftext_value(
    archive: FArchive,
    tolerant: bool = True,
) -> tuple[str, int, int, int]:
    """读取完整 FText，返回 (value, flags, history_type, consumed)。"""
    start_pos = archive.tell()
    flags = archive.read_i32()
    history_type_raw = archive.read_u8()
    history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
    value, _ = read_ftext_with_history(archive, history_type, tolerant=tolerant)
    return value, flags, history_type, archive.tell() - start_pos


def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
) -> tuple[str, int]:
    """读取 FText，返回 (值, 消耗字节数)。

    history_type (ETextHistoryType, signed int8):
    - -1 (0xFF): None（无历史）- bHasCultureInvariantString (bool=4 bytes) + optional FString
    - 0: Base - Namespace (FString) + Key (FString) + SourceString (FString)
    - 1: NamedFormat - FormatText (递归 FText) + Arguments (TArray<FFormatArgumentData>)
    - 2+: 其他生成类型（在 tolerant 模式下不解析）

    参考 UE C++ 源码:
    - Text.cpp L850-1044: FText::SerializeText
    - TextHistory.cpp L792-861: FTextHistory_Base::Serialize
    - TextHistory.cpp L1150-1169: FTextHistory_NamedFormat::Serialize
    - Text.cpp L1680-1761: FFormatArgumentData 序列化
    """
    start_pos = archive.tell()
    value = ""

    if history_type not in range(-1, 11):
        raise ParseError(f"Invalid FText history_type={history_type} at pos {start_pos}")

    if history_type in (-1, 255):
        b_has_culture = archive.read_bool()
        if b_has_culture:
            value = _read_ftext_fstring(archive)
    elif history_type == 0:
        _namespace = _read_ftext_fstring(archive)
        _key = _read_ftext_fstring(archive)
        value = _read_ftext_fstring(archive)
    elif history_type == 1:
        format_text, _, _, _ = _read_ftext_value(archive, tolerant=tolerant)
        arg_count = archive.read_i32()
        if arg_count < 0 or arg_count > MAX_SAFE_COUNT:
            # 设计决策：从 raise ParseError 改为 warning+skip，
            # 与项目整体 tolerant 模式对齐，避免损坏数据导致解析完全中断
            logger.debug(
                "FText NamedFormat arg_count=%d exceeds limit %d, skipping args",
                arg_count, MAX_SAFE_COUNT
            )
            arg_count = 0  # 跳过后续参数读取
        format_args: Dict[str, str] = {}
        for _ in range(arg_count):
            arg_name = _read_ftext_fstring(archive)
            arg_type = archive.read_u8()
            arg_value = ""
            if arg_type == 0:
                arg_value = str(archive.read_i64())
            elif arg_type == 1:
                arg_value = str(archive.read_u64())
            elif arg_type == 2:
                arg_value = str(archive.read_f32())
            elif arg_type == 3:
                arg_value = str(archive.read_f64())
            elif arg_type == 4:
                arg_value, _, _, _ = _read_ftext_value(archive, tolerant=tolerant)
            elif arg_type == 5:
                arg_value = str(archive.read_u8())
            else:
                raise ParseError(f"Unsupported FFormatArgumentType={arg_type}")
            format_args[arg_name] = arg_value
        value = format_text
        for key, arg in format_args.items():
            if key:
                value = value.replace("{" + key + "}", arg)
    else:
        raise ParseError(f"Unsupported FText history_type={history_type}")

    consumed = archive.tell() - start_pos
    return value, consumed


# ============================================================================
# Pin 引用校验辅助
# ============================================================================

def validate_pin_reference_at(
    archive: FArchive,
    pos: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
) -> Optional[Dict[str, Any]]:
    """校验指定位置的 PinReference 结构有效性。

    不移动指针，只检查指定位置是否符合 PinReference 格式：
    - b_null (i32): 0 表示正常引用，非 0 表示空引用（仅 4 字节）
    - owning_node (i32): 在 import/export 范围内（仅当 b_null == 0）
    - pin_guid (16 bytes): 非全零（除非是 ParentPin 空引用）

    支持 4 字节 null PinReference（b_null != 0 时仅需 4 字节）。

    Returns:
        None: 无效结构
        Dict: {
            "b_null": int,
            "owning_node": int,
            "owning_node_valid": bool,
            "guid_nonzero": bool,
            "valid": bool,
            "reason": str,
            "serialized_size": int,  # 4 for null, 24 for non-null
        }
    """
    import struct

    current_pos = archive.tell()

    file_size = getattr(archive, "_file_size", getattr(archive, "file_size", 0))

    # 至少需要 4 字节读取 b_null
    if file_size and pos + 4 > file_size:
        archive.seek(current_pos)
        return None

    fmt = '>' if getattr(archive, '_byte_swapping', False) else '<'

    archive.seek(pos)
    header_bytes = archive.read(4)
    b_null = struct.unpack(f'{fmt}i', header_bytes[0:4])[0]

    if b_null != 0:
        # Null PinReference: 仅消耗 4 字节
        archive.seek(current_pos)
        return {
            "b_null": b_null,
            "owning_node": 0,
            "owning_node_valid": True,
            "guid_nonzero": False,
            "valid": True,
            "reason": "valid null ref (b_null!=0, no actual pin)",
            "serialized_size": 4,
        }

    # b_null == 0: 需要完整 24 字节
    if file_size and pos + 24 > file_size:
        archive.seek(current_pos)
        return None

    archive.seek(pos)
    header_bytes = archive.read(24)
    archive.seek(current_pos)

    owning_node = struct.unpack(f'{fmt}i', header_bytes[4:8])[0]
    guid_bytes = header_bytes[8:24]
    guid_nonzero = any(b != 0 for b in guid_bytes)

    # 校验 owning_node 范围
    owning_node_abs = abs(owning_node)
    export_count = len(export_map)
    import_count = len(import_map) if import_map else 0
    max_valid_index = export_count + import_count + 50  # 允许一定余量

    owning_node_valid = (
        owning_node == 0 or  # 0 表示无引用
        owning_node_abs < max_valid_index
    )

    # 校验 b_null 语义
    if not owning_node_valid:
        valid = False
        reason = f"owning_node {owning_node} exceeds range 0..{max_valid_index}"
    elif not guid_nonzero:
        # b_null == 0 但 GUID 全零：可能是 ParentPin 空引用或未初始化
        valid = True
        reason = "valid ref with zero guid (parent pin empty)"
    else:
        valid = True
        reason = "valid pin reference"

    return {
        "b_null": b_null,
        "owning_node": owning_node,
        "owning_node_valid": owning_node_valid,
        "guid_nonzero": guid_nonzero,
        "valid": valid,
        "reason": reason,
        "serialized_size": 24,
    }


# ============================================================================
# UEdGraph 读取
# ============================================================================

def _extract_graph_properties(
    graph_export: ObjectExport,
) -> tuple:
    """从已解析的 PropertyTag 数据中提取 UEdGraph 字段。

    UEdGraph 的 Schema、Nodes、GraphGuid 在 UE 中声明为 UPROPERTY，
    因此以 PropertyTag 形式序列化在 export body 中。直接从
    graph_export.properties 读取，避免二次从 archive 二进制解析。

    Returns:
        (schema_name, node_indices, graph_guid_str)
        schema_name: Schema import 的全名，如 "EdGraphSchema_K2"，未找到时为 None
        node_indices: 节点的1-based export index 列表
        graph_guid_str: GraphGuid 的 hex 字符串（小写无 dash），未找到时为 ""
    """
    schema_name: Optional[str] = None
    node_indices: List[int] = []
    graph_guid: str = ""

    props = getattr(graph_export, "properties", None) or []
    for prop in props:
        name = getattr(prop, "name", None) or (prop.get("name") if isinstance(prop, dict) else None)
        value = getattr(prop, "value", None) or (prop.get("value") if isinstance(prop, dict) else None)
        if name == "Schema" and value is not None:
            # ObjectProperty → import reference
            if isinstance(value, dict):
                schema_name = value.get("object_name") or value.get("full_name")
            elif isinstance(value, int):
                # 未解析的 PackageIndex (legacy)
                pass
        elif name == "Nodes" and isinstance(value, list):
            node_indices = [v for v in value if isinstance(v, int) and v > 0]
        elif name == "GraphGuid" and isinstance(value, dict):
            fields = value.get("fields", {})
            if fields:
                a = fields.get("A", 0) & 0xFFFFFFFF
                b = fields.get("B", 0) & 0xFFFFFFFF
                c = fields.get("C", 0) & 0xFFFFFFFF
                d = fields.get("D", 0) & 0xFFFFFFFF
                graph_guid = (
                    f"{a & 0xFF:02x}{(a >> 8) & 0xFF:02x}{(a >> 16) & 0xFF:02x}{(a >> 24) & 0xFF:02x}"
                    f"{b & 0xFF:02x}{(b >> 8) & 0xFF:02x}-{(c >> 8) & 0xFF:02x}{c & 0xFF:02x}"
                    f"-{(c >> 24) & 0xFF:02x}{(c >> 16) & 0xFF:02x}-{(d >> 8) & 0xFF:02x}{d & 0xFF:02x}"
                    f"-{(d >> 24) & 0xFF:02x}{(d >> 16) & 0xFF:02x}{(d >> 8) & 0xFF:02x}{d & 0xFF:02x}"
                )

    return schema_name, node_indices, graph_guid


def read_ue_graph(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    graph_export: ObjectExport,
    graph_class: str,
    graph_export_idx: int = 0,
    linker: Optional["PackageLinker"] = None,
    _parsed_indices: Optional[set] = None,
) -> UEdGraph:
    """读取 UEdGraph 容器（EdGraph.cpp）。

    Schema / Nodes / GraphGuid 均为 UPROPERTY，由 PropertyTag 解析器
    在 preload 阶段提取到 graph_export.properties 中。此函数从已解析
    的属性中获取这些字段，不再从 archive 二进制读取。

    节点数据仍通过 archive.seek(node_export.serial_offset) 读取
    （节点 export 的 script_serial + pins 是独立的二进制段）。

    参考 UE C++ UEdGraph::Serialize() 实现
    """
    # 延迟导入避免循环依赖
    from uasset_read.serializers.graph_node import read_ue_graph_node  # noqa: F811

    if _parsed_indices is None:
        _parsed_indices = set()
    _parsed_indices.add(graph_export_idx)

    # ── 1. 从 PropertyTag 提取 Schema / Nodes / GraphGuid ──
    schema_name, node_indices, graph_guid = _extract_graph_properties(graph_export)

    # 解析 Schema 引用
    schema: Optional[str] = schema_name

    # ── 2. 按 node_indices 读取每个节点的二进制数据 ──
    if len(node_indices) > MAX_NODES_PER_GRAPH:
        logger.debug("node_indices count %d exceeds MAX_NODES_PER_GRAPH %d, truncating",
                       len(node_indices), MAX_NODES_PER_GRAPH)
        node_indices = node_indices[:MAX_NODES_PER_GRAPH]

    nodes: List[UEdGraphNode] = []

    for node_index in node_indices:
        if node_index <= 0 or node_index > len(export_map):
            continue
        node_export = export_map[node_index - 1]
        try:
            node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)
            node._export_index = node_index  # tag for dedup
            nodes.append(node)
        except (ParseError, struct.error, OSError, ValueError, KeyError):
            logger.debug("Failed to read node %s (export #%d) in graph %s",
                           node_export.object_name, node_index, graph_export.object_name)

    # UE 5.x fallback: scan export_map for nodes whose outer is this graph.
    # Catches nodes not listed in the Nodes PropertyTag (e.g. dynamically added nodes).
    if graph_export_idx > 0:
        for node_export in export_map:
            if node_export.outer_index.index == graph_export_idx:
                node_class = _gac(node_export, import_map, export_map, linker)
                if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
                    node_idx = export_map.index(node_export) + 1
                    already_collected = any(
                        getattr(n, '_export_index', None) == node_idx
                        for n in nodes
                    )
                    if already_collected:
                        continue
                    try:
                        node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)
                        node._export_index = node_idx  # tag for dedup
                        nodes.append(node)
                    except (ParseError, struct.error, OSError, ValueError, KeyError):
                        nodes.append(UEdGraphNode(
                            node_guid="",
                            node_pos_x=0,
                            node_pos_y=0,
                            node_comment="",
                            pins=[],
                            class_name=node_class or "",
                            node_data={"_parse_error": True, "node_name": node_export.object_name},
                        ))
                        nodes[-1]._export_object_name = node_export.object_name

    # ── 3. bEditable / SubGraphs — 从 PropertyTag 或 fallback 读取 ──
    # 这些字段可能是 WITH_EDITORONLY_DATA，未必存在于 PropertyTag 中。
    # 当 Properties 中有时直接取值；否则默认 bEditable=True、SubGraphs=[]。
    b_editable = True  # 默认值
    subgraph_indices: List[int] = []

    props = getattr(graph_export, "properties", None) or []
    for prop in props:
        pname = getattr(prop, "name", None) or (prop.get("name") if isinstance(prop, dict) else None)
        pvalue = getattr(prop, "value", None) or (prop.get("value") if isinstance(prop, dict) else None)
        if pname == "bEditable":
            b_editable = bool(pvalue) if pvalue is not None else True
        elif pname == "SubGraphs" and isinstance(pvalue, list):
            if len(pvalue) > MAX_SUBGRAPHS:
                logger.debug(
                    "SubGraphs count %d exceeds limit %d, truncating",
                    len(pvalue), MAX_SUBGRAPHS,
                )
                pvalue = pvalue[:MAX_SUBGRAPHS]
            subgraph_indices = [v for v in pvalue if isinstance(v, int) and v > 0]

    # 6. 解析子图（合并 SubGraphs 数组 + AnimGraphNode 嵌套子图）
    subgraphs: List[UEdGraph] = []

    # 6a. 从 SubGraphs 数组解析（直接序列化的子图引用）
    for pkg_idx in subgraph_indices:
        if pkg_idx <= 0 or pkg_idx > len(export_map):
            continue
        if pkg_idx in _parsed_indices:
            continue

        subgraph_export = export_map[pkg_idx - 1]
        subgraph_class = _gac(subgraph_export, import_map, export_map, linker) or ""

        if not (subgraph_class.endswith("Graph") or subgraph_class == "EdGraph" or subgraph_class == "UberEdGraph"):
            continue

        try:
            subgraph = read_ue_graph(
                archive, name_map, summary, export_map, import_map,
                subgraph_export, subgraph_class, pkg_idx, linker,
                _parsed_indices=_parsed_indices,
            )
            subgraphs.append(subgraph)
        except (struct.error, OSError, ValueError, KeyError) as e:
            logger.debug("Failed to parse SubGraphs entry %d: %s", pkg_idx, e)

    # 6b. 从 AnimGraphNode node_data.subgraph_references 解析
    for node in nodes:
        node_data = getattr(node, "node_data", None)
        if not isinstance(node_data, dict):
            continue

        subgraph_refs = node_data.get("subgraph_references", {})
        for ref_key, ref_info in subgraph_refs.items():
            if not isinstance(ref_info, dict) or "error" in ref_info:
                continue

            pkg_idx = ref_info.get("package_index", 0)
            if pkg_idx <= 0 or pkg_idx > len(export_map):
                continue
            if pkg_idx in _parsed_indices:
                continue

            subgraph_export = export_map[pkg_idx - 1]
            subgraph_class = _gac(subgraph_export, import_map, export_map, linker) or ""

            if not (subgraph_class.endswith("Graph") or subgraph_class == "EdGraph" or subgraph_class == "UberEdGraph"):
                continue

            try:
                subgraph = read_ue_graph(
                    archive, name_map, summary, export_map, import_map,
                    subgraph_export, subgraph_class, pkg_idx, linker,
                    _parsed_indices=_parsed_indices,
                )
                subgraph.graph_name = f"{node.node_comment or node.class_name}.{ref_key}"
                subgraphs.append(subgraph)
            except (struct.error, OSError, ValueError, KeyError) as e:
                logger.debug("Failed to parse subgraph %s: %s", ref_info.get("object_name", ""), e)

    return UEdGraph(
        graph_name=graph_export.object_name,
        graph_class=graph_class,
        schema=schema,
        nodes=nodes,
        graph_guid=graph_guid,
        b_editable=b_editable,
        subgraphs=subgraphs,
    )


# ============================================================================
# 向后兼容 re-exports — 从 graph_pin.py 和 graph_node.py 重新导出
#
# ⚠️ 循环依赖脆弱性：
# graph_node.py 和 graph_pin.py 内部通过延迟导入引用本模块 (graph.py) 的辅助函数，
# 本模块又通过 re-exports 反向引用它们。这个循环依赖由 Python 的模块缓存机制
# 隐式容忍，但任何导入顺序变化（如调整 import 位置或拆分 helper 到新模块）都可能
# 导致 ImportError。修改此区域前务必验证 `python -c "from uasset_read.serializers.graph import *"`。
# ============================================================================

from uasset_read.serializers.graph_pin import (  # noqa: E402, F401
    read_ed_graph_pin_type,
    read_pin_reference,
    read_pin_array,
    read_ue_graph_pin,
)
from uasset_read.serializers.graph_node import (  # noqa: E402, F401
    read_ue_graph_node,
    create_node_from_archive,
    read_fmember_reference,
    read_k2node_call_function,
    read_k2node_event,
    read_k2node_knot,
    read_edgraph_node_comment,
    read_k2node_enhanced_input,
    read_k2node_functionentry,
    read_k2node_message,
    read_k2node_call_delegate,
    read_k2node_call_array_function,
    read_k2node_call_parent_function,
    read_k2node_function_result,
    read_k2node_create_widget,
    read_k2node_add_delegate,
    read_k2node_macro_instance,
    read_k2node_assign_delegate,
    read_k2node_get_data_table_row,
    read_k2node_load_asset,
    read_k2node_spawn_actor_from_class,
)
