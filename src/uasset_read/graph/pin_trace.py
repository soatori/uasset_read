"""Pin 字段级诊断入口。

Pin 字段 offset 追踪（成功/失败都记录）。
字段级诊断基线 —— 每个 graph 的节点类型计数、关键节点字段详情、
          每个 pin 的 LinkedTo 起点 offset、失败 count、recovery reason。
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional


def write_pin_trace_report(
    asset_path: str,
    output_path: Optional[str] = None,
    *,
    tolerant: bool = True,
) -> Dict[str, Any]:
    """解析资产并写出 Pin 字段 offset 诊断报告。

    诊断产物默认写入仓库 `temp/`，不改变解析器默认输出。
    """
    from uasset_read import parse_uasset_with_linker
    from uasset_read.serializers.graph import (
        get_pin_trace_events,
        reset_pin_trace_events,
    )

    asset = Path(asset_path)
    if output_path is None:
        repo_root = Path(__file__).resolve().parents[3]
        output = repo_root / "temp" / f"{asset.stem}-pin-trace.json"
    else:
        output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    old_env = os.environ.get("UASSET_READ_PIN_TRACE")
    os.environ["UASSET_READ_PIN_TRACE"] = "1"
    reset_pin_trace_events()
    try:
        result = parse_uasset_with_linker(str(asset), tolerant=tolerant)
        events = get_pin_trace_events()
    finally:
        if old_env is None:
            os.environ.pop("UASSET_READ_PIN_TRACE", None)
        else:
            os.environ["UASSET_READ_PIN_TRACE"] = old_env

    pins = events["pins"]
    recoveries = events["recoveries"]
    report: Dict[str, Any] = {
        "asset": str(asset),
        "is_success": getattr(result, "is_success", False),
        "errors": list(getattr(result, "errors", [])),
        "summary": {
            "graphs": len(getattr(result, "graphs", [])),
            "pins_traced": len(pins),
            "linkedto_refs": sum(item.get("linkedto_count", 0) for item in pins),
            "subpins_refs": sum(item.get("subpins_count", 0) for item in pins),
            "recoveries": len(recoveries),
            "p73_recovery_events": sum(
                1 for item in recoveries if item.get("kind") == "pin_array_count"
            ),
            "p73_subpins_events": sum(
                1 for item in recoveries if item.get("kind") == "subpins_resync"
            ),
        },
        "pins": pins,
        "recoveries": recoveries,
    }

    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report["output_path"] = str(output)
    return report


# ============================================================================
# 字段级诊断基线
# ============================================================================

def _classify_node(node) -> str:
    """返回节点的语义分类标签。"""
    class_name = getattr(node, "class_name", "")
    data = getattr(node, "node_data", {}) or {}
    if class_name == "K2Node_EnhancedInputAction":
        return data.get("input_action_path", class_name)
    if class_name == "K2Node_Event":
        ref = data.get("event_reference")
        if ref:
            member = getattr(ref, "member_name", "") or str(ref)
            return f"Event:{member}"
        return class_name
    if class_name == "K2Node_FunctionEntry":
        ref = data.get("function_reference")
        if ref:
            member = getattr(ref, "member_name", "") or str(ref)
            return f"FunctionEntry:{member}"
        return class_name
    if class_name == "EdGraphNode_Comment":
        comment = data.get("node_comment", "") or getattr(node, "node_comment", "")
        return f"Comment:{comment}" if comment else class_name
    return class_name


def _pin_direction_label(direction) -> str:
    """将 direction 整数转换为标签，标注异常值。"""
    labels = {0: "Input", 1: "Output"}
    if direction in labels:
        return labels[direction]
    return f"ANOMALY({direction})"


def _pin_category_label(pin) -> str:
    """获取 pin 的 category 字符串。"""
    pt = getattr(pin, "pin_type", None)
    if pt is None:
        return ""
    return getattr(pt, "pin_category", "") or ""


def _pin_subcategory_label(pin) -> str:
    """获取 pin 的 subcategory 字符串。"""
    pt = getattr(pin, "pin_type", None)
    if pt is None:
        return ""
    return getattr(pt, "pin_subcategory", "") or ""


def _pin_default_label(pin) -> str:
    """获取 pin 的 default object / default value 摘要。"""
    default_obj = getattr(pin, "default_object", 0) or 0
    default_val = getattr(pin, "default_value", "") or ""
    if default_obj != 0:
        return f"DefaultObject={default_obj}"
    if default_val:
        return f"DefaultValue={default_val[:40]}"
    return ""


def _collect_linkedto_failures_from_log(log_handler) -> List[Dict[str, Any]]:
    """从日志 handler 中提取 LinkedTo read failed 事件。"""
    failures = []
    records = getattr(log_handler, "buffer", []) or []
    for record in records:
        msg = record.getMessage()
        if "LinkedTo read failed" in msg:
            # 提取位置信息
            import re
            pos_match = re.search(r"pos (\d+)", msg)
            pos = int(pos_match.group(1)) if pos_match else -1
            failures.append({
                "pos": pos,
                "message": msg,
            })
    return failures


def write_phase75_diagnostic(
    asset_path: str,
    output_dir: Optional[str] = None,
    *,
    tolerant: bool = True,
) -> Dict[str, Any]:
    """字段级诊断基线。

    输出到 output_dir（默认 temp/phase75/）：
    - graph_node_counts.json: 每个 graph 的节点类型计数
    - enhanced_input_nodes.json: K2Node_EnhancedInputAction 字段详情
    - event_nodes.json: K2Node_Event 字段详情
    - function_entry_nodes.json: K2Node_FunctionEntry 字段详情
    - pin_diagnostics.json: 每个 pin 的 LinkedTo 起点 offset、失败、recovery
    - linkedto_recovery_summary.txt: LinkedTo read failed 汇总
    - event_node_fields.json: 事件节点字段详情（含 EventReference、bOverrideFunction）

    复用 trace_mode=True，扩展为成功/失败都记录。
    不改变解析结果；trace_mode=False/True 的 graph/node/pin/link 数量一致。
    """
    from uasset_read import parse_uasset_with_linker
    from uasset_read.serializers.graph import (
        get_pin_trace_events,
        reset_pin_trace_events,
    )

    repo_root = Path(__file__).resolve().parents[3]
    if output_dir is None:
        output_dir = str(repo_root / "temp" / "phase75")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 启用 trace_mode 并捕获日志
    old_env = os.environ.get("UASSET_READ_PIN_TRACE")
    os.environ["UASSET_READ_PIN_TRACE"] = "1"
    reset_pin_trace_events()

    import logging
    log_handler = logging.handlers.MemoryHandler(capacity=10000)
    root_logger = logging.getLogger("uasset_read")
    root_logger.addHandler(log_handler)
    root_logger.setLevel(logging.DEBUG)

    try:
        result = parse_uasset_with_linker(str(asset_path), tolerant=tolerant)
        events = get_pin_trace_events()
    finally:
        if old_env is None:
            os.environ.pop("UASSET_READ_PIN_TRACE", None)
        else:
            os.environ["UASSET_READ_PIN_TRACE"] = old_env
        root_logger.removeHandler(log_handler)

    graphs = getattr(result, "graphs", [])
    pins_traced = events.get("pins", [])
    recoveries = events.get("recoveries", [])
    log_failures = _collect_linkedto_failures_from_log(log_handler)
    log_handler.flush()

    # ========== 1. Graph 节点类型计数 ==========
    graph_counts = []
    for graph in graphs:
        graph_name = getattr(graph, "graph_name", "")
        counter = Counter()
        for node in getattr(graph, "nodes", []):
            counter[getattr(node, "class_name", "Unknown")] += 1
        graph_counts.append({
            "graph": graph_name,
            "total_nodes": len(getattr(graph, "nodes", [])),
            "node_type_counts": dict(counter),
        })

    graph_counts_path = out / "graph_node_counts.json"
    graph_counts_path.write_text(
        json.dumps(graph_counts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ========== 2. K2Node_EnhancedInputAction 字段详情 ==========
    enhanced_input_nodes = []
    for graph in graphs:
        for node in getattr(graph, "nodes", []):
            if getattr(node, "class_name", "") != "K2Node_EnhancedInputAction":
                continue
            data = getattr(node, "node_data", {}) or {}
            pins_info = []
            for pin in getattr(node, "pins", []):
                pin_name = getattr(pin, "pin_name", "")
                direction = getattr(pin, "direction", None)
                linked_to_count = len(getattr(pin, "linked_to_raw", []) or [])
                sub_pins_count = len(getattr(pin, "sub_pins", []) or [])
                pin_info = {
                    "pin_name": pin_name,
                    "direction": direction,
                    "direction_label": _pin_direction_label(direction),
                    "category": _pin_category_label(pin),
                    "subcategory": _pin_subcategory_label(pin),
                    "default": _pin_default_label(pin),
                    "linked_to_count": linked_to_count,
                    "sub_pins_count": sub_pins_count,
                }
                # 检查 split pin 状态（ParentPin）
                parent = getattr(pin, "parent_pin", None)
                if parent:
                    pin_info["parent_pin"] = parent.get("owning_node", "")
                pins_info.append(pin_info)

            # 提取 AdvancedPinDisplay
            advanced_display = data.get("AdvancedPinDisplay", data.get("advanced_pin_display"))
            if isinstance(advanced_display, dict):
                advanced_display = advanced_display.get("size", "unknown")

            enhanced_input_nodes.append({
                "graph": getattr(graph, "graph_name", ""),
                "node_class": "K2Node_EnhancedInputAction",
                "node_guid": getattr(node, "node_guid", ""),
                "node_export_name": getattr(node, "_export_object_name", ""),
                "input_action_path": data.get("input_action_path", ""),
                "advanced_pin_display": advanced_display,
                "pin_count": len(pins_info),
                "pins": pins_info,
                "trigger_events": data.get("trigger_events", {}),
            })

    enhanced_input_path = out / "enhanced_input_nodes.json"
    enhanced_input_path.write_text(
        json.dumps(enhanced_input_nodes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ========== 3. K2Node_Event 字段详情 ==========
    event_nodes = []
    for graph in graphs:
        for node in getattr(graph, "nodes", []):
            if getattr(node, "class_name", "") != "K2Node_Event":
                continue
            data = getattr(node, "node_data", {}) or {}
            event_ref = data.get("event_reference")
            event_ref_info = {}
            if event_ref:
                event_ref_info = {
                    "member_parent": getattr(event_ref, "member_parent", ""),
                    "member_name": getattr(event_ref, "member_name", ""),
                    "member_guid": getattr(event_ref, "member_guid", ""),
                    "b_self_context": getattr(event_ref, "b_self_context", False),
                }

            b_override = data.get("b_override_function", None)

            # 检查 split pin 状态
            split_pins = []
            for pin in getattr(node, "pins", []):
                parent = getattr(pin, "parent_pin", None)
                if parent and parent.get("owning_node"):
                    split_pins.append({
                        "pin_name": getattr(pin, "pin_name", ""),
                        "parent_pin": parent.get("owning_node", ""),
                        "direction": _pin_direction_label(getattr(pin, "direction", None)),
                    })

            event_nodes.append({
                "graph": getattr(graph, "graph_name", ""),
                "node_class": "K2Node_Event",
                "node_guid": getattr(node, "node_guid", ""),
                "node_export_name": getattr(node, "_export_object_name", ""),
                "event_reference": event_ref_info,
                "b_override_function": b_override,
                "b_override_source": "property_tag" if b_override is not None else "default_missing",
                "pin_count": len(getattr(node, "pins", [])),
                "split_pins": split_pins,
            })

    event_nodes_path = out / "event_nodes.json"
    event_nodes_path.write_text(
        json.dumps(event_nodes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ========== 4. K2Node_FunctionEntry 字段详情 ==========
    function_entry_nodes = []
    for graph in graphs:
        for node in getattr(graph, "nodes", []):
            if getattr(node, "class_name", "") != "K2Node_FunctionEntry":
                continue
            data = getattr(node, "node_data", {}) or {}
            func_ref = data.get("function_reference")
            func_ref_info = {}
            if func_ref:
                func_ref_info = {
                    "member_parent": getattr(func_ref, "member_parent", ""),
                    "member_name": getattr(func_ref, "member_name", ""),
                    "member_guid": getattr(func_ref, "member_guid", ""),
                }

            pins_info = []
            for pin in getattr(node, "pins", []):
                pins_info.append({
                    "pin_name": getattr(pin, "pin_name", ""),
                    "direction": _pin_direction_label(getattr(pin, "direction", None)),
                    "category": _pin_category_label(pin),
                })

            function_entry_nodes.append({
                "graph": getattr(graph, "graph_name", ""),
                "node_class": "K2Node_FunctionEntry",
                "node_guid": getattr(node, "node_guid", ""),
                "node_export_name": getattr(node, "_export_object_name", ""),
                "function_reference": func_ref_info,
                "extra_flags": data.get("ExtraFlags", data.get("extra_flags")),
                "b_is_editable": data.get("bIsEditable", data.get("b_is_editable")),
                "pin_count": len(pins_info),
                "pins": pins_info,
            })

    func_entry_path = out / "function_entry_nodes.json"
    func_entry_path.write_text(
        json.dumps(function_entry_nodes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ========== 5. Pin 诊断详情 ==========
    pin_diagnostics = []
    for trace in pins_traced:
        pin_info = {
            "pin_name": trace.get("pin_name", ""),
            "pin_id": trace.get("pin_id", ""),
            "pin_start_pos": trace.get("pin_start_pos", -1),
            "node_name": trace.get("node_name", ""),
            "node_guid": trace.get("node_guid", ""),
            "node_class": trace.get("node_class", ""),
            "linkedto_start": trace.get("linkedto_start", -1),
            "linkedto_raw_count": trace.get("linkedto_raw_count"),
            "linkedto_count": trace.get("linkedto_count", 0),
            "subpins_start": trace.get("subpins_start", -1),
            "subpins_raw_count": trace.get("subpins_raw_count"),
            "subpins_count": trace.get("subpins_count", 0),
            "first_misaligned": trace.get("first_misaligned", ""),
        }
        # 标注哪些字段有异常
        anomalous_fields = []
        for field in trace.get("fields", []):
            if field.get("exception"):
                anomalous_fields.append({
                    "name": field["name"],
                    "start": field.get("start", -1),
                    "end": field.get("end", -1),
                    "consumed": field.get("consumed", -1),
                })
        pin_info["anomalous_fields"] = anomalous_fields
        pin_diagnostics.append(pin_info)

    pin_diag_path = out / "pin_diagnostics.json"
    pin_diag_path.write_text(
        json.dumps(pin_diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ========== 6. LinkedTo recovery 汇总 ==========
    recovery_lines = []
    recovery_lines.append(f"LinkedTo Recovery Summary")
    recovery_lines.append(f"=" * 50)
    recovery_lines.append(f"Asset: {asset_path}")
    recovery_lines.append(f"Total pins traced: {len(pins_traced)}")
    recovery_lines.append(f"Total recovery events: {len(recoveries)}")
    recovery_lines.append(f"Log LinkedTo read failed: {len(log_failures)}")
    recovery_lines.append("")

    # 按 kind 分组
    kind_counter = Counter()
    for r in recoveries:
        kind_counter[r.get("kind", "unknown")] += 1
    recovery_lines.append("Recovery events by kind:")
    for kind, count in kind_counter.most_common():
        recovery_lines.append(f"  {kind}: {count}")
    recovery_lines.append("")

    # 列出所有 LinkedTo read failed 日志条目
    if log_failures:
        recovery_lines.append("LinkedTo read failed log entries:")
        for i, failure in enumerate(log_failures, 1):
            recovery_lines.append(f"  [{i}] pos={failure['pos']}: {failure['message'][:120]}")
        recovery_lines.append("")

    # 找出第一个异常 LinkedTo offset 对应的 graph/node/pin
    if pins_traced:
        recovery_lines.append("First anomalous LinkedTo offsets:")
        for trace in pins_traced[:50]:  # 只看前 50 个有 trace 的 pin
            raw_count = trace.get("linkedto_raw_count")
            count = trace.get("linkedto_count", 0)
            if raw_count is not None and (raw_count < 0 or raw_count > 100):
                recovery_lines.append(
                    f"  Pin '{trace.get('pin_name')}' at {trace.get('linkedto_start')}: "
                    f"raw_count={raw_count}, resolved_count={count}, "
                    f"node={trace.get('node_name')}, class={trace.get('node_class')}"
                )
        recovery_lines.append("")

    # Recovery 详情
    if recoveries:
        recovery_lines.append("Recovery details:")
        for i, r in enumerate(recoveries[:30], 1):  # 前 30 条
            recovery_lines.append(f"  [{i}] kind={r.get('kind')}, reason={r.get('reason', '')[:80]}")
            if "context" in r:
                recovery_lines.append(f"      context={r['context']}")
            if "bad_count" in r:
                recovery_lines.append(f"      bad_count={r['bad_count']}")
            if "candidate_pos" in r:
                recovery_lines.append(f"      candidate_pos={r['candidate_pos']}")
        recovery_lines.append("")

    recovery_txt_path = out / "linkedto_recovery_summary.txt"
    recovery_txt_path.write_text("\n".join(recovery_lines), encoding="utf-8")

    # ========== 7. event_node_fields.json (Pin body offset 和 recovery reason) ==========
    # 为每个 pin trace 关联到具体 event node，标注 recovery reason
    event_node_fields = []
    for trace in pins_traced:
        node_class = trace.get("node_class", "")
        if node_class not in ("K2Node_Event", "K2Node_EnhancedInputAction", "K2Node_FunctionEntry", "EdGraphNode_Comment"):
            continue

        # 查找该 pin 相关的 recovery 事件
        related_recoveries = []
        for r in recoveries:
            # 简单关联：通过 pin_start_pos 附近的 candidate_pos
            cand_pos = r.get("candidate_pos", r.get("recovered_pos", -1))
            pin_start = trace.get("pin_start_pos", -1)
            linkedto_start = trace.get("linkedto_start", -1)
            if pin_start >= 0 and 0 <= (cand_pos - pin_start) < 500:
                related_recoveries.append({
                    "kind": r.get("kind"),
                    "reason": r.get("reason", ""),
                    "confidence": r.get("confidence", ""),
                    "candidate_pos": cand_pos,
                })

        field_detail = {
            "pin_name": trace.get("pin_name", ""),
            "node_name": trace.get("node_name", ""),
            "node_class": node_class,
            "node_guid": trace.get("node_guid", ""),
            "pin_start_pos": trace.get("pin_start_pos", -1),
            "linkedto_start": trace.get("linkedto_start", -1),
            "linkedto_raw_count": trace.get("linkedto_raw_count"),
            "linkedto_count": trace.get("linkedto_count", 0),
            "first_misaligned": trace.get("first_misaligned", ""),
            "anomalous_field_count": len([f for f in trace.get("fields", []) if f.get("exception")]),
            "related_recoveries": related_recoveries,
            "fields": trace.get("fields", []),
        }
        event_node_fields.append(field_detail)

    event_fields_path = out / "event_node_fields.json"
    event_fields_path.write_text(
        json.dumps(event_node_fields, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ========== 8. pin_body_offsets.json (字段 offset 详情) ==========
    pin_body_offsets = []
    for trace in pins_traced:
        offsets = {
            "pin_name": trace.get("pin_name", ""),
            "node_name": trace.get("node_name", ""),
            "node_class": trace.get("node_class", ""),
            "pin_start_pos": trace.get("pin_start_pos", -1),
            "linkedto_start": trace.get("linkedto_start", -1),
            "subpins_start": trace.get("subpins_start", -1),
            "fields": [],
        }
        for f in trace.get("fields", []):
            offsets["fields"].append({
                "name": f["name"],
                "start": f.get("start", -1),
                "end": f.get("end", -1),
                "consumed": f.get("consumed", -1),
                "value_preview": f.get("value", "")[:50],
                "exception": f.get("exception", False),
                "fallback": f.get("fallback", False),
            })
        pin_body_offsets.append(offsets)

    body_offsets_path = out / "pin_body_offsets.json"
    body_offsets_path.write_text(
        json.dumps(pin_body_offsets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ========== 返回汇总 ==========
    return {
        "output_dir": str(out),
        "files_created": [
            str(graph_counts_path),
            str(enhanced_input_path),
            str(event_nodes_path),
            str(func_entry_path),
            str(pin_diag_path),
            str(recovery_txt_path),
            str(event_fields_path),
            str(body_offsets_path),
        ],
        "summary": {
            "graphs": len(graphs),
            "total_nodes": sum(len(getattr(g, "nodes", [])) for g in graphs),
            "pins_traced": len(pins_traced),
            "recoveries": len(recoveries),
            "linkedto_log_failures": len(log_failures),
            "enhanced_input_nodes": len(enhanced_input_nodes),
            "event_nodes": len(event_nodes),
            "function_entry_nodes": len(function_entry_nodes),
        },
    }
