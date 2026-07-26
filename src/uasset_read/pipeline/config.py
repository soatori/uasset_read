"""parse_utils.py — 轻量解析辅助函数。"""
from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.models.config import ParseConfig

from uasset_read.constants import (
    LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD,
    CONTROL_RIG_LARGE_FILE_THRESHOLD,
    CONTROL_RIG_LARGE_FILE_CLASSES,
)

logger = logging.getLogger(__name__)


def _should_use_lightweight_tolerant_parse(
    result,
    tolerant: bool,
    lightweight_threshold: int | None = None,
    force_full_parse: bool = False,
) -> bool:
    if force_full_parse:
        return False
    if not tolerant or result.summary is None:
        return False
    threshold = (
        lightweight_threshold
        if lightweight_threshold is not None
        else LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
    )
    # ControlRig 等大型文件：检测 export 类名，使用更高的阈值
    if (
        threshold == LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
        and lightweight_threshold is None
        and _is_large_file_asset(result)
    ):
        threshold = CONTROL_RIG_LARGE_FILE_THRESHOLD
    return getattr(result.summary, "export_count", 0) > threshold


def _is_large_file_asset(result) -> bool:
    """检测是否为 ControlRig/RigVM 等天然大型文件资产。

    通过 export 类名子串匹配判断，避免将这类资产误判为超大蓝图。
    参考: UE ControlRig.cpp 序列化结构。
    """
    from uasset_read.serializers.object_resources import resolve_class_name
    export_map = getattr(result, "export_map", None) or []
    import_map = getattr(result, "import_map", None) or []
    # 仅检查前 20 个 export 的类名即可判断（避免全量扫描性能开销）
    for export in export_map[:20]:
        try:
            class_name = resolve_class_name(
                export.class_index, import_map, export_map
            )
        except (AttributeError, TypeError, IndexError):
            continue
        if class_name and any(sub in class_name for sub in CONTROL_RIG_LARGE_FILE_CLASSES):
            return True
    return False


def _build_lightweight_graphs(result) -> list:
    """在轻量模式下提取基本图信息（仅名称）。"""
    from uasset_read.serializers.object_resources import get_asset_class
    from uasset_read.models.core import UEdGraph

    graphs = []
    if not result.export_map or not result.import_map:
        return graphs

    for export in result.export_map:
        name = str(getattr(export, "object_name", "") or "")
        if not name:
            continue

        # 检测 EdGraph 类型导出
        class_name = get_asset_class(export, result.import_map, result.export_map)
        if class_name in ("EdGraph", "UberEdGraph"):
            # 创建最小化的 UEdGraph，仅包含名称
            graph = UEdGraph(
                graph_name=name,
                graph_class=class_name,
                nodes=[],
            )
            graphs.append(graph)

    return graphs


def _build_lightweight_function_graphs(export_map) -> list[dict]:
    entries = []
    for export in export_map or []:
        name = str(getattr(export, "object_name", "") or "")
        if not name or name.endswith("_C") or name.startswith("Default__"):
            continue
        if name in {"EventGraph", "UberGraphPages", "SimpleConstructionScript"}:
            continue
        entries.append({
            "function_name": name,
            "graph_source": "export_map",
            "entry_node_guid": "",
            "signature": {"return_type": "", "parameters": []},
            "execution_flows": [],
            "fallback_reason": "lightweight_tolerant_parse",
        })
        if len(entries) >= 64:
            break
    return entries


def _apply_lightweight_parse(
    result,
    tolerant: bool,
    lightweight_threshold: int | None,
    force_full_parse: bool,
) -> bool:
    """轻量解析路径：若触发则填充 result 并返回 True。"""
    if not _should_use_lightweight_tolerant_parse(result, tolerant, lightweight_threshold, force_full_parse):
        return False
    result.warnings.append(
        "Lightweight tolerant parse used due to export complexity "
        f"(exports={getattr(result.summary, 'export_count', 0)})"
    )
    result.metadata["lightweight_tolerant_parse"] = True
    result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(result.export_map)
    result.graphs = _build_lightweight_graphs(result)
    if result.graphs and result.export_map:
        for export in result.export_map:
            name = str(getattr(export, "object_name", "") or "")
            if name.endswith("_C") and not name.startswith("Default__"):
                export.graphs = result.graphs
                break
    result.is_success = not result.errors
    return True


def _resolve_parse_params(
    config: ParseConfig | None,
    kwargs: dict,
) -> dict:
    """将 ParseConfig 和旧风格关键字参数合并为最终参数字典。

    - 若提供 config，config 的值作为默认，显式传入的旧参数可覆盖。
    - 若未提供 config，旧参数保持原样。
    - 对同时从 config 和旧参数传入的值，发出 DeprecationWarning。

    kwargs 中值为 None 的条目视为"调用方未指定"，不覆盖 config 值。
    """
    if config is None:
        return kwargs

    # 所有旧参数在 parse_package() 签名中默认为 None（哨兵），
    # 只有调用方显式传入非 None 值才算"显式覆盖"。
    # 但如果调用方显式传入了与 config 值不同的非 None 值，发出弃用警告。
    conflicting = []
    for fld in config.__dataclass_fields__:
        if fld in kwargs and kwargs[fld] is not None:
            config_val = getattr(config, fld)
            if config_val is not None and kwargs[fld] != config_val:
                conflicting.append(fld)

    if conflicting:
        warnings.warn(
            f"同时传入 config 和旧参数 {conflicting}，旧参数将覆盖 config 中的对应值。"
            "请统一使用 ParseConfig。",
            DeprecationWarning,
            stacklevel=3,
        )

    # 合并：kwargs 非 None 值覆盖 config，None 不覆盖
    merged = {}
    for fld in config.__dataclass_fields__:
        kw_val = kwargs.get(fld)
        merged[fld] = kw_val if kw_val is not None else getattr(config, fld)
    # 保留 kwargs 中不在 config 中的键（如 path, provider 等）
    for key in kwargs:
        if key not in merged:
            merged[key] = kwargs[key]
    return merged
