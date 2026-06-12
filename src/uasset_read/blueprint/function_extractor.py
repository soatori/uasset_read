"""蓝图函数/事件提取模块。"""
from __future__ import annotations

from typing import Any, List, Optional

from uasset_read.models.blueprint import BlueprintFunction, BlueprintEvent, FunctionParameter
from uasset_read.models.properties import StructValue
from ._variable_types import map_pin_category_to_cpp_type


def extract_functions_from_bpgc_properties(properties: List[Any]) -> List[BlueprintFunction]:
    """从 BPGC export 属性中提取函数。

    查找 UbergraphFunction 和 FunctionList 属性。
    """
    functions: List[BlueprintFunction] = []
    for prop in properties:
        prop_name = getattr(prop, 'name', '')
        if prop_name == "UbergraphFunction":
            func_name = _resolve_property_to_function_name(prop.value)
            if func_name:
                functions.append(BlueprintFunction(name=func_name))
        elif prop_name == "FunctionList" and isinstance(prop.value, (list, tuple)):
            for item in prop.value:
                func_name = _resolve_property_to_function_name(item)
                if func_name:
                    functions.append(BlueprintFunction(name=func_name))
    return functions


def _resolve_property_to_function_name(value: Any) -> Optional[str]:
    """将属性值解析为函数名字符串。"""
    if value is None:
        return None
    if isinstance(value, str) and value and value != "None":
        raw = value.split('/')[-1] if '/' in value else value
        return raw.split('.')[-1] if '.' in raw else raw
    if isinstance(value, dict):
        obj_name = value.get('object_name') or value.get('resolved') or value.get('raw_index')
        if obj_name and obj_name != "None":
            raw = str(obj_name)
            return raw.split('.')[-1] if '.' in raw else raw
    if hasattr(value, 'object_name'):
        name = getattr(value, 'object_name', None)
        if name and name != "None":
            raw = str(name)
            return raw.split('.')[-1] if '.' in raw else raw
    return None


def extract_functions_from_graphs(graphs) -> List[BlueprintFunction]:
    """从图的 K2Node_FunctionEntry 和 K2Node_Event 节点提取函数元数据。"""
    if not graphs:
        return []
    functions: List[BlueprintFunction] = []
    for graph in graphs:
        for node in getattr(graph, 'nodes', []):
            class_name = getattr(node, 'class_name', '')
            if class_name not in ("K2Node_FunctionEntry", "K2Node_Event"):
                continue

            nd = node.node_data or {}
            if not isinstance(nd, dict):
                continue

            is_event_node = class_name == "K2Node_Event"

            func_name = "Unknown"
            if is_event_node:
                er = nd.get("event_reference")
                if er and hasattr(er, 'member_name'):
                    mn = er.member_name
                    func_name = mn.split('/')[-1] if '/' in mn else mn
                    if func_name == "None":
                        func_name = nd.get("custom_function_name", "Unknown")
                elif nd.get("custom_function_name"):
                    func_name = nd["custom_function_name"]
            else:
                fr = nd.get("function_reference")
                if fr and hasattr(fr, 'member_name'):
                    func_name = fr.member_name if fr.member_name != "None" else "Unknown"
                else:
                    func_name = nd.get("function_name", nd.get("custom_function_name", "Unknown"))

            parameters: List[FunctionParameter] = []
            return_type = ""

            for pin in getattr(node, 'pins', []):
                pin_dir = getattr(pin, 'direction', '')
                pin_type_obj = getattr(pin, 'pin_type', None)
                pin_type_name = ""
                if pin_type_obj and hasattr(pin_type_obj, 'pin_category'):
                    pin_type_name = getattr(pin_type_obj, 'pin_category', '') or ""
                elif isinstance(pin_type_obj, dict):
                    pin_type_name = pin_type_obj.get("pin_category", pin_type_obj.get("category", ""))

                if isinstance(pin_dir, int):
                    is_output = pin_dir == 1
                    is_input = pin_dir == 0
                else:
                    is_output = pin_dir == "EGPD_Output"
                    is_input = pin_dir == "EGPD_Input"

                if pin_type_name.lower() in ("exec", "delegate", "multicastdelegate"):
                    continue

                pin_name = getattr(pin, 'pin_name', '')
                pin_name_lower = pin_name.lower()

                if not is_event_node and is_output:
                    if "return" in pin_name_lower:
                        if return_type == "":
                            return_type = map_pin_category_to_cpp_type(pin_type_name)
                    else:
                        cpp_type = map_pin_category_to_cpp_type(pin_type_name)
                        parameters.append(FunctionParameter(
                            name=pin_name,
                            param_type=cpp_type,
                            is_input=False,
                            is_output=True,
                        ))
                elif is_input:
                    if pin_name_lower in ("self", "target", "worldcontext"):
                        continue
                    cpp_type = map_pin_category_to_cpp_type(pin_type_name)
                    parameters.append(FunctionParameter(
                        name=pin_name,
                        param_type=cpp_type,
                        is_input=True,
                        is_output=False,
                    ))
                elif is_output and is_event_node:
                    cpp_type = map_pin_category_to_cpp_type(pin_type_name)
                    parameters.append(FunctionParameter(
                        name=pin_name,
                        param_type=cpp_type,
                        is_input=False,
                        is_output=True,
                    ))

            func = BlueprintFunction(
                name=func_name,
                return_type=return_type,
                parameters=parameters,
            )
            if is_event_node:
                func.is_blueprint_implementable_event = True
                if nd.get("b_override_function", False):
                    func.is_blueprint_event = True
            functions.append(func)
    return functions


def build_events_from_functions(functions: List[BlueprintFunction]) -> List[BlueprintEvent]:
    """从函数列表构建事件列表。"""
    events: List[BlueprintEvent] = []
    for f in functions:
        if f.is_blueprint_implementable_event or f.is_blueprint_event:
            events.append(BlueprintEvent(
                name=f.name,
                event_type="Override" if f.is_blueprint_event else "Event",
                function_flags=f.function_flags,
                is_blueprint_event=f.is_blueprint_event,
                is_blueprint_implementable_event=f.is_blueprint_implementable_event,
                parameters=f.parameters,
            ))
    return events


def deduplicate_functions(
    functions_bpgc: List[BlueprintFunction],
    functions_graph: List[BlueprintFunction],
) -> List[BlueprintFunction]:
    """按名称去重函数列表。"""
    seen_names: set[str] = set()
    functions: List[BlueprintFunction] = []
    for func in functions_bpgc + functions_graph:
        if func.name not in seen_names:
            seen_names.add(func.name)
            functions.append(func)
    return functions
