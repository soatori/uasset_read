"""从 UE5.8 源码提取 K2Node 类型列表和继承关系。

扫描 BlueprintGraph + AnimGraph + AIGraph 模块的 K2Node*.h 文件，
使用 regex 提取类声明和继承关系，输出 JSON 数据。

Usage:
    python scripts/extract_k2node_types.py --source-root "D:/Program Files/Epic Games/Engine/UE_5.8/Engine/Source"
    python scripts/extract_k2node_types.py --source-root "..." --output temp/k2node_types_data.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Regex: class UK2NodeXXX : public UK2Node | UK2NodeBase | UEdGraphNode
# Must match: UK2Node (base), UK2Node_CallFunction, UEdGraphNode
CLASS_RE = re.compile(
    r"class\s+(UK2Node\w*)\s*:\s*public\s+(UK2Node\w*|UEdGraphNode\w*)"
)

# 特殊语义映射: class_name → 缩短后的枚举名
# 这些是 UE 源码中类名与常用语义名称不一致的情况
SEMANTIC_RENAMES: dict[str, str] = {
    "K2Node_IfThenElse": "Branch",
    "K2Node_ExecutionSequence": "Sequence",
    "K2Node_SwitchInteger": "SwitchInt",
    "K2Node_SwitchString": "SwitchString",
    "K2Node_SwitchEnum": "SwitchEnum",
    "K2Node_SwitchName": "SwitchName",
    "K2Node_DoOnceMultiInput": "DoOnce",
    "K2Node_CommutativeAssociativeBinaryOperator": "BinaryOperator",
    "K2Node_ForEachElementInEnum": "ForEachEnum",
    "K2Node_ConstructObjectFromClass": "ConstructObject",
    "K2Node_SpawnActorFromClass": "SpawnActorFromClass",
    "K2Node_GenericCreateObject": "GenericCreateObject",
    "K2Node_GetEnumeratorNameAsString": "GetEnumeratorNameAsString",
    "K2Node_GetEnumeratorName": "GetEnumeratorName",
    "K2Node_GetNumEnumEntries": "GetNumEnumEntries",
    "K2Node_EnumEquality": "EnumEquality",
    "K2Node_EnumInequality": "EnumInequality",
    "K2Node_PureAssignmentStatement": "PureAssignmentStatement",
    "K2Node_AssignmentStatement": "AssignmentStatement",
    "K2Node_SetFieldsInStruct": "SetFieldsInStruct",
    "K2Node_StructMemberGet": "StructMemberGet",
    "K2Node_StructMemberSet": "StructMemberSet",
    "K2Node_MakeStruct": "MakeStruct",
    "K2Node_BreakStruct": "BreakStruct",
    "K2Node_MakeArray": "MakeArray",
    "K2Node_MakeMap": "MakeMap",
    "K2Node_MakeSet": "MakeSet",
    "K2Node_MakeContainer": "MakeContainer",
    "K2Node_GetArrayItem": "GetArrayItem",
    "K2Node_MapForEach": "MapForEach",
    "K2Node_SetForEach": "SetForEach",
    "K2Node_VariableGet": "VariableGet",
    "K2Node_VariableSet": "VariableSet",
    "K2Node_VariableSetRef": "VariableSetRef",
    "K2Node_CallFunction": "CallFunction",
    "K2Node_CallArrayFunction": "CallArrayFunction",
    "K2Node_CallDelegate": "CallDelegate",
    "K2Node_CallParentFunction": "CallParentFunction",
    "K2Node_CallFunctionOnMember": "CallFunctionOnMember",
    "K2Node_CallDataTableFunction": "CallDataTableFunction",
    "K2Node_CallMaterialParameterCollectionFunction": "CallMaterialParameterCollectionFunction",
    "K2Node_Message": "Message",
    "K2Node_GetInputAxisValue": "GetInputAxisValue",
    "K2Node_GetInputAxisKeyValue": "GetInputAxisKeyValue",
    "K2Node_GetInputVectorAxisValue": "GetInputVectorAxisValue",
    "K2Node_PromotableOperator": "PromotableOperator",
    "K2Node_AddComponent": "AddComponent",
    "K2Node_AddComponentByClass": "AddComponentByClass",
    "K2Node_DynamicCast": "DynamicCast",
    "K2Node_ClassDynamicCast": "ClassDynamicCast",
    "K2Node_CastByteToEnum": "CastByteToEnum",
    "K2Node_Event": "Event",
    "K2Node_CustomEvent": "CustomEvent",
    "K2Node_ActorBoundEvent": "ActorBoundEvent",
    "K2Node_ComponentBoundEvent": "ComponentBoundEvent",
    "K2Node_GeneratedBoundEvent": "GeneratedBoundEvent",
    "K2Node_InputActionEvent": "InputActionEvent",
    "K2Node_InputAxisEvent": "InputAxisEvent",
    "K2Node_InputKeyEvent": "InputKeyEvent",
    "K2Node_InputTouchEvent": "InputTouchEvent",
    "K2Node_InputVectorAxisEvent": "InputVectorAxisEvent",
    "K2Node_FunctionEntry": "FunctionEntry",
    "K2Node_FunctionResult": "FunctionResult",
    "K2Node_FunctionTerminator": "FunctionTerminator",
    "K2Node_EditablePinBase": "EditablePinBase",
    "K2Node_MacroInstance": "MacroInstance",
    "K2Node_Tunnel": "Tunnel",
    "K2Node_TunnelBoundary": "TunnelBoundary",
    "K2Node_Composite": "Composite",
    "K2Node_LoadAsset": "LoadAsset",
    "K2Node_LoadAssetClass": "LoadAssetClass",
    "K2Node_LoadAssets": "LoadAssets",
    "K2Node_ConvertAsset": "ConvertAsset",
    "K2Node_FormatText": "FormatText",
    "K2Node_GenericToText": "GenericToText",
    "K2Node_GetDataTableRow": "GetDataTableRow",
    "K2Node_Knot": "Knot",
    "K2Node_TemporaryVariable": "TemporaryVariable",
    "K2Node_Copy": "Copy",
    "K2Node_DeadClass": "DeadClass",
    "K2Node_MakeVariable": "MakeVariable",
    "K2Node_SetVariableOnPersistentFrame": "SetVariableOnPersistentFrame",
    "K2Node_InstancedStruct": "InstancedStruct",
    "K2Node_LocalVariable": "LocalVariable",
    "K2Node_MathExpression": "MathExpression",
    "K2Node_EnumLiteral": "EnumLiteral",
    "K2Node_BitmaskLiteral": "BitmaskLiteral",
    "K2Node_Self": "Self",
    "K2Node_Literal": "Literal",
    "K2Node_InputAction": "InputAction",
    "K2Node_InputAxis": "InputAxis",
    "K2Node_InputKey": "InputKey",
    "K2Node_InputTouch": "InputTouch",
    "K2Node_EnhancedInputAction": "EnhancedInputAction",
    "K2Node_GetSubsystem": "GetSubsystem",
    "K2Node_GetSubsystemFromPC": "GetSubsystemFromPC",
    "K2Node_GetEngineSubsystem": "GetEngineSubsystem",
    "K2Node_GetEditorSubsystem": "GetEditorSubsystem",
    "K2Node_GetClassDefaults": "GetClassDefaults",
    "K2Node_AsyncAction": "AsyncAction",
    "K2Node_BaseAsyncTask": "BaseAsyncTask",
    "K2Node_Timeline": "Timeline",
    "K2Node_PlayMontage": "PlayMontage",
    "K2Node_AddDelegate": "AddDelegate",
    "K2Node_CreateDelegate": "CreateDelegate",
    "K2Node_ClearDelegate": "ClearDelegate",
    "K2Node_RemoveDelegate": "RemoveDelegate",
    "K2Node_AssignDelegate": "AssignDelegate",
    "K2Node_BaseMCDelegate": "BaseMCDelegate",
    "K2Node_Select": "Select",
    "K2Node_MultiGate": "MultiGate",
    "K2Node_SpawnActor": "SpawnActor",
    "K2Node_Variable": "Variable",
    "K2Node_StructOperation": "StructOperation",
    "K2Node_AnimGetter": "AnimGetter",
    "K2Node_AnimNodeReference": "AnimNodeReference",
    "K2Node_TransitionRuleGetter": "TransitionRuleGetter",
    "K2Node_AIMoveTo": "AIMoveTo",
    "K2Node_CreateWidget": "CreateWidget",
    "K2Node_CreateDragDropOperation": "CreateDragDropOperation",
    "K2Node_EditorPropertyAccessBase": "EditorPropertyAccessBase",
    "K2Node_GetSequenceBinding": "GetSequenceBinding",
    "K2Node_LatentGameplayTaskCall": "LatentGameplayTaskCall",
    "K2Node_PlayAnimation": "PlayAnimation",
    "K2Node_WidgetAnimationEvent": "WidgetAnimationEvent",
}


def default_enum_name(class_name: str) -> str:
    """默认枚举名：去掉 K2Node_ 前缀。"""
    return class_name.replace("K2Node_", "")


def get_enum_name(class_name: str) -> str:
    """获取 class_name 对应的枚举名（含特殊语义映射）。"""
    return SEMANTIC_RENAMES.get(class_name, default_enum_name(class_name))


def scan_directory(directory: Path) -> list[tuple[str, str]]:
    """扫描目录中的 K2Node*.h 文件，提取类型和父类。

    Returns:
        List of (class_name, parent_class_name) tuples
    """
    results = []
    if not directory.is_dir():
        return results

    for header in sorted(directory.glob("K2Node*.h")):
        try:
            content = header.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        match = CLASS_RE.search(content)
        if match:
            class_name = match.group(1)  # UK2NodeXXX
            parent_class = match.group(2)  # UK2NodeYYY or UEdGraphNode
            # Remove leading 'U' prefix for consistency with naming
            # Keep the full name as-is from source
            results.append((class_name, parent_class))

    return results


def extract_k2node_types(ue_source_root: Path) -> dict:
    """从 UE 源码提取 K2Node 类型列表和继承关系。

    Args:
        ue_source_root: UE5.8 Engine/Source 根目录

    Returns:
        {
            "types": ["K2Node_CallFunction", ...],
            "inheritance": {"K2Node_CallArrayFunction": "K2Node_CallFunction", ...},
            "enum_names": {"K2Node_CallFunction": "CallFunction", ...},
            "stats": {"files_scanned": N, "modules": {...}}
        }
    """
    all_classes: list[tuple[str, str]] = []
    stats = {"files_scanned": 0, "modules": {}}

    # 定义扫描模块及其路径 — 覆盖 BlueprintGraph + AnimGraph + AIGraph + UMGEditor + MovieSceneTools + GameplayTasksEditor
    modules = [
        ("BlueprintGraph", ue_source_root / "Editor/BlueprintGraph/Classes"),
        ("BlueprintGraph-Private", ue_source_root / "Editor/BlueprintGraph/Private"),
        ("AnimGraph", ue_source_root / "Editor/AnimGraph/Public"),
        ("AIGraph", ue_source_root / "Editor/AIGraph/Public"),
        ("UMGEditor", ue_source_root / "Editor/UMGEditor/Classes"),
        ("UMGEditor-Nodes", ue_source_root / "Editor/UMGEditor/Private/Nodes"),
        ("MovieSceneTools", ue_source_root / "Editor/MovieSceneTools/Public"),
        ("GameplayTasksEditor", ue_source_root / "Editor/GameplayTasksEditor/Classes"),
    ]

    for module_name, module_dir in modules:
        classes = scan_directory(module_dir)
        module_stats = {"classes_found": len(classes), "path": str(module_dir)}
        stats["modules"][module_name] = module_stats
        stats["files_scanned"] += len(list(module_dir.glob("K2Node*.h"))) if module_dir.is_dir() else 0
        all_classes.extend(classes)
        print(f"  [{module_name}] {len(classes)} classes from {module_dir.name}/")

    # 构建数据结构
    types_set: set[str] = set()
    inheritance: dict[str, str] = {}
    enum_names: dict[str, str] = {}

    for class_name, parent_class in all_classes:
        # 跳过接口类（继承自 UInterface）
        if parent_class == "UInterface":
            continue
        # class_name without leading 'U' for data keys
        key = class_name[1:]  # Remove 'U' prefix → K2Node_XXX
        types_set.add(key)
        enum_names[key] = get_enum_name(key)

        if parent_class == "UEdGraphNode":
            # 直接继承 UEdGraphNode → 父类为 K2Node（基类）
            inheritance[key] = "K2Node"
        else:
            # UK2NodeXXX → K2Node_XXX
            parent_key = parent_class[1:]
            inheritance[key] = parent_key

    # 添加 K2Node 基类（不来自具体 header，但作为继承链根）
    types_set.add("K2Node")
    enum_names["K2Node"] = "K2NodeBase"
    # K2Node 继承自 UEdGraphNode，但在我们的枚举中作为根
    # Do NOT add K2Node to inheritance (it's the root, no parent in our domain)
    if "K2Node" in inheritance:
        del inheritance["K2Node"]

    types = sorted(types_set)

    return {
        "types": types,
        "inheritance": inheritance,
        "enum_names": enum_names,
        "stats": stats,
    }


def validate_no_cycles(inheritance: dict[str, str]) -> list[str]:
    """验证继承关系无循环。返回检测到的循环（应空）。"""
    cycles = []
    for start in inheritance:
        visited: set[str] = set()
        current = start
        while current in inheritance:
            if current in visited:
                cycles.append(f"{start} -> ... -> {current} (cycle)")
                break
            visited.add(current)
            current = inheritance[current]
    return cycles


def compute_max_depth(inheritance: dict[str, str]) -> int:
    """计算继承链最大深度。"""
    max_depth = 0
    for key in inheritance:
        depth = 0
        current = key
        visited: set[str] = set()
        while current in inheritance:
            if current in visited:
                break
            visited.add(current)
            current = inheritance[current]
            depth += 1
        max_depth = max(max_depth, depth)
    return max_depth


def main():
    parser = argparse.ArgumentParser(
        description="Extract K2Node types from UE5.8 source code"
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("D:/Program Files/Epic Games/Engine/UE_5.8/Engine/Source"),
        help="UE5.8 Engine/Source root directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (default: stdout)",
    )
    args = parser.parse_args()

    if not args.source_root.is_dir():
        print(f"ERROR: Source root not found: {args.source_root}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning UE5.8 source: {args.source_root}")

    data = extract_k2node_types(args.source_root)

    # 验证
    cycles = validate_no_cycles(data["inheritance"])
    max_depth = compute_max_depth(data["inheritance"])

    print(f"\nResults:")
    print(f"  Types: {len(data['types'])}")
    print(f"  Inheritance relations: {len(data['inheritance'])}")
    print(f"  Enum name mappings: {len(data['enum_names'])}")
    print(f"  Max inheritance depth: {max_depth}")
    print(f"  Cycle check: {'PASS' if not cycles else 'FAIL - ' + str(cycles)}")

    # 统计各模块
    for mod_name, mod_stats in data["stats"]["modules"].items():
        print(f"  [{mod_name}] {mod_stats['classes_found']} classes")

    if cycles:
        print("\nWARNING: Cycles detected in inheritance!", file=sys.stderr)
        for c in cycles:
            print(f"  {c}", file=sys.stderr)

    output_json = json.dumps(data, indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json, encoding="utf-8")
        print(f"\nOutput written to: {args.output}")
    else:
        print("\n--- JSON output ---")
        print(output_json)

    # 返回验证结果
    if len(data["types"]) < 100:
        print(f"\nWARNING: Expected 100+ types, got {len(data['types'])}", file=sys.stderr)
        sys.exit(1)

    if cycles:
        sys.exit(2)

    print(f"\nValidation PASSED: {len(data['types'])} types, no cycles")


if __name__ == "__main__":
    main()
