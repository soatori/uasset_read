"""
C++ 类骨架提取模块 — extract_cpp_class_skeleton()。

Per D-02: 沿 ClassParent 追溯继承链。
Per D-03: 使用 ue_path_to_cpp_type 进行类型映射。
Per D-04: 使用 cpf_flags_to_uproperty_marks 获取 UPROPERTY 标记。
Per D-05: 构建完整的 header_meta。
从图节点提取方法声明填充 methods。
从 decompiled_functions 注入函数体到 body_text。

导出：
    extract_cpp_class_skeleton: LinkerParseResult → CppClassIR 提取函数
"""
from __future__ import annotations

import re
import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Tuple

from uasset_read.cpp_gen.formatters import (
    CppClassIR,
    CppProperty,
    CppHeaderMeta,
    CppMethodIR,
    CppCallParameter,
    CppCallStatement,
)
from uasset_read.cpp_gen.cpp_type_mapper import (
    ue_path_to_cpp_type,
    ue_package_path_to_cpp_class,
    infer_class_prefix,
)
from uasset_read.cpp_gen.cpp_uproperty_mapper import (
    cpf_flags_to_uproperty_marks,
)
from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
    build_component_creations,
    build_component_assignments,
    build_default_values,
    build_transform_assignments,
)
from uasset_read.cpp_gen.cpp_constructor_formatter import (
    format_cpp_constructor,
)
from uasset_read.cpp_gen.sanitizer import sanitize_identifier
from uasset_read.constants import CPF_InstancedReference

if TYPE_CHECKING:
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.models.blueprint import BlueprintMetadata, BlueprintVariable
    from uasset_read.models.core import FEdGraphPinType

logger = logging.getLogger(__name__)

# ============================================================================
# 继承链深度限制（T-056-03）
# ============================================================================

MAX_INHERITANCE_DEPTH = 50  # 防止无限循环


# ============================================================================
# 从 decompiled_functions 补齐缺失方法（第三条路径）
# ============================================================================

def _backfill_missing_methods(
    methods: List[CppMethodIR],
    decompiled_functions: List[Any],
) -> None:
    """从 decompiled_functions 补齐 extract_cpp_functions 遗漏的 CppMethodIR。

    原因：extract_cpp_functions 只处理 K2Node_FunctionEntry 和
    K2Node_Event(b_override=True)，但部分反编译函数无对应图节点
    （如 ExecuteUbergraph、UserConstructionScript、InputAction 事件）。
    """
    existing_names = {m.cpp_name for m in methods}
    for decompiled in decompiled_functions:
        sanitized = _sanitize_identifier(decompiled.function_name)
        if sanitized not in existing_names:
            methods.append(CppMethodIR(
                cpp_name=sanitized,
                return_type="void",
                parameters=[],
                ufunction_specifiers=[],
                is_override=False,
                body_text=decompiled.cpp_code or "/* no source available */",
            ))
            existing_names.add(sanitized)


# ============================================================================
# 核心提取函数
# ============================================================================

def extract_cpp_class_skeleton(result: "LinkerParseResult") -> CppClassIR:
    """从 LinkerParseResult 提取 C++ 类骨架。

    Per D-02: 从 BlueprintMetadata.parent_class 追溯继承链。
    Per D-03: 将 UE 类型映射为 C++ 类型名。
    Per D-04: 将 CPF 标志转换为 UPROPERTY 标记。
    Per D-05: 构建 header_meta（includes + generated_include）。
    从图节点提取方法声明填充 methods。

    Args:
        result: LinkerParseResult（来自 parse_uasset_with_linker）

    Returns:
        CppClassIR: C++ 类骨架中间表示

    Raises:
        ValueError: 如果 result.blueprint 为 None 或不是蓝图
    """
    # 验证输入
    if result.blueprint is None:
        raise ValueError("LinkerParseResult.blueprint is None — cannot extract skeleton")
    if not result.blueprint.is_blueprint:
        raise ValueError("LinkerParseResult.blueprint.is_blueprint is False — not a blueprint")

    blueprint = result.blueprint

    # 1. 提取类名
    class_name = _extract_class_name(result)

    # 2. 解析继承链（Per D-02）
    parent_class = _resolve_parent_class(blueprint, result.linker)

    # 3. 提取组件属性
    properties: List[CppProperty] = []
    properties.extend(_extract_component_properties(blueprint, result.components))

    # 4. 提取变量属性
    properties.extend(_extract_variable_properties(blueprint))

    # 5. 提取输入动作变量（从图节点）
    if result.graphs:
        properties.extend(_extract_input_action_properties(result.graphs))

    # 6. 提取方法声明
    methods: List[CppMethodIR] = []
    if result.graphs:
        blueprint_functions = getattr(blueprint, 'functions', None)
        methods = extract_cpp_functions(
            result.graphs,
            blueprint_functions=blueprint_functions,
            linker=result.linker,
        )

    # 6. 补齐缺失方法（第三条路径 — 从 decompiled_functions 直接生成 CppMethodIR）
    if hasattr(result, 'decompiled_functions') and result.decompiled_functions:
        _backfill_missing_methods(methods, result.decompiled_functions)

    # 6. 注入函数体（从 decompiled_functions）
    if methods and hasattr(result, 'decompiled_functions') and result.decompiled_functions:
        _inject_function_bodies(methods, result.decompiled_functions)

    # 6.1 设置 class_name（用于 .cpp 实现中 ClassName::Method 前缀）
    for method in methods:
        if not method.class_name:
            method.class_name = class_name

    # 7. 构建 header_meta（Per D-05）
    header_meta = CppHeaderMeta.build_from_parent(parent_class, class_name)

    # 7. 构建 CppClassIR
    ir = CppClassIR(
        name=class_name,
        parent_class=parent_class,
        header_meta=header_meta,
        properties=properties,
        methods=methods,
        constructor={
            "component_creations": [],
            "component_assignments": [],
            "default_values": [],
        },  # 填充
    )

    # 填充 constructor 字典
    components = result.components or []
    ir.constructor["component_creations"] = build_component_creations(ir)
    ir.constructor["component_assignments"] = build_component_assignments(components)
    ir.constructor["default_values"] = build_default_values(ir, blueprint.variables)

    # Blocker 2 fix: transform 数据也流入 default_values
    ir.constructor["default_values"].extend(build_transform_assignments(ir, components))

    # 生成完整构造函数文本
    ir.constructor["constructor_text"] = format_cpp_constructor(ir)

    return ir


# ============================================================================
# 蓝图元数据过滤器（P0 改进）
# ============================================================================

# 蓝图内部元数据属性，不应作为 C++ 成员变量输出
BLUEPRINT_METADATA_KEYS = frozenset({
    # 蓝图系统属性
    'BlueprintSystemVersion',
    'BlueprintGuid',
    'bLegacyNeedToPurgeSkelRefs',
    'bEnforceConstCorrectness',
    # 构造脚本
    'SimpleConstructionScript',
    # 图相关
    'UbergraphPages',
    'FunctionGraphs',
    'NewVariables',
    'CategorySorting',
    'LastEditedDocuments',
    'ImplementedInterfaces',
    # 缩略图和类引用
    'ThumbnailInfo',
    'GeneratedClass',
    'PropertyGuids',
    # Ubergraph
    'UbergraphFunction',
    'UbergraphFrame',
})


def _is_blueprint_metadata(prop_name: str) -> bool:
    """判断属性是否为蓝图内部元数据。

    Args:
        prop_name: 属性名

    Returns:
        True 如果是蓝图元数据（应过滤掉）
    """
    return prop_name in BLUEPRINT_METADATA_KEYS


# ============================================================================
# 组件名称清理（P1 改进）
# ============================================================================

# 需要移除的组件名称后缀模式
_COMPONENT_SUFFIX_PATTERNS = [
    (re.compile(r'_GEN_VARIABLE$'), ''),
    (re.compile(r'_\d+__[A-F0-9]+$'), ''),  # _0__CCE3C0B4 等哈希后缀
    (re.compile(r'_\d+$'), ''),  # _0 等数字后缀
]


def _clean_component_name(name: str) -> str:
    """清理组件名称，移除 UE 内部后缀。

    Examples:
        CameraComponent_0__CCE3C0B4 -> CameraComponent
        FirstPersonMesh_GEN_VARIABLE -> FirstPersonMesh
        Arrow_1 -> Arrow

    Args:
        name: 原始组件名

    Returns:
        清理后的名称
    """
    cleaned = name
    for pattern, replacement in _COMPONENT_SUFFIX_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned if cleaned else name


# ============================================================================
# 类名简化（P0 改进）
# ============================================================================

def _simplify_class_name(raw_name: str) -> str:
    """简化类名，从完整包路径提取简洁名称。

    Examples:
        /Game/FirstPerson/Blueprints/BP_FirstPersonCharacter -> BP_FirstPersonCharacter
        Game_FirstPerson_Blueprints_BP_FirstPersonCharacter -> BP_FirstPersonCharacter

    Args:
        raw_name: 原始名称（可能包含路径）

    Returns:
        简化后的类名
    """
    # 移除路径前缀
    if '/' in raw_name:
        raw_name = raw_name.rsplit('/', 1)[-1]

    # 移除点号分隔的扩展名
    if '.' in raw_name:
        raw_name = raw_name.rsplit('.', 1)[0]

    # 替换非法字符为下划线
    cleaned = re.sub(r'[^A-Za-z0-9_]', '_', raw_name)

    # 确保以有效字符开头
    if cleaned and cleaned[0].isdigit():
        cleaned = '_' + cleaned

    return cleaned


# ============================================================================
# 辅助函数
# ============================================================================

def _build_param_name_map(method: CppMethodIR) -> Dict[str, str]:
    """构建 {原始参数名模式 -> sanitized名} 映射。

    Sanitizer 将 '/' 等非法字符替换为 '__'。例如：
    - 'Left / Right' → 'Left__Right'
    - 'Forward / Backward' → 'Forward__Backward'

    反向推导：如果 sanitized 名包含 '__'，构造对应的 ' / ' 模式。
    """
    name_map = {}
    for param in method.parameters:
        if '__' in param.name:
            # 反向推导原始名：'__' → ' / '
            original = param.name.replace('__', ' / ')
            name_map[original] = param.name
    return name_map


def _inject_function_bodies(
    methods: List[CppMethodIR],
    decompiled_functions: List[Any],
) -> None:
    """将 KismetDecompiledResult 的 cpp_code 注入到 CppMethodIR.body_text。

    匹配逻辑：
    1. 精确匹配：function_name == cpp_name
    2. 清理后匹配：function_name 清理后 == cpp_name
    3. 大小写不敏感匹配

    注入前执行符号映射替换，确保函数体内变量名与方法声明一致。

    Args:
        methods: CppMethodIR 列表（已填充方法声明）
        decompiled_functions: KismetDecompiledResult 列表（含 cpp_code）
    """
    method_index: Dict[str, CppMethodIR] = {m.cpp_name: m for m in methods}

    for decompiled in decompiled_functions:
        func_name = decompiled.function_name

        # 精确匹配
        method = method_index.get(func_name)

        # 清理后匹配
        if method is None:
            sanitized = _sanitize_identifier(func_name)
            method = method_index.get(sanitized)

        # 大小写不敏感匹配
        if method is None:
            for cpp_name, m in method_index.items():
                if func_name.lower() == cpp_name.lower():
                    method = m
                    break

        if method and decompiled.cpp_code:
            body = decompiled.cpp_code
            # 执行符号映射替换：原始参数名 → sanitized 名
            for original, sanitized in _build_param_name_map(method).items():
                body = body.replace(original, sanitized)
            method.body_text = body

def _extract_class_name(result: "LinkerParseResult") -> str:
    """提取 C++ 类名。

    根据蓝图名称和父类类型确定 C++ 前缀：
    - 使用 infer_class_prefix 从父类名推导前缀（A/U/F/E/I）
    - 如果简化后的名称已有正确的 UE 前缀，不重复添加
    - 否则添加推导的前缀

    Args:
        result: LinkerParseResult

    Returns:
        C++ 类名（带前缀）
    """
    # 从 summary.package_name 或 name_map[0] 获取名称
    raw_name = ""
    if result.summary and hasattr(result.summary, 'package_name'):
        raw_name = result.summary.package_name
    elif result.name_map and len(result.name_map) > 0:
        raw_name = result.name_map[0]

    if not raw_name:
        logger.warning("Could not determine class name from result")
        return "UUnknownClass"

    # 简化类名
    clean_name = _simplify_class_name(raw_name)

    # 从父类推导前缀（使用 infer_class_prefix 统一逻辑）
    parent_class_path = result.blueprint.parent_class or ""
    parent_cpp = ue_package_path_to_cpp_class(parent_class_path)
    prefix = infer_class_prefix(parent_cpp)

    # 如果名称已有该前缀，不重复添加
    if clean_name.startswith(prefix):
        return clean_name

    return f"{prefix}{clean_name}"


def _resolve_parent_class(
    blueprint: "BlueprintMetadata",
    linker: Optional[Any]
) -> str:
    """解析父类名。

    Per D-02: 从 blueprint.parent_class 提取并转换为 C++ 类名。
    未来支持通过 linker 深度追溯继承链（当前仅直接父类）。

    Args:
        blueprint: BlueprintMetadata
        linker: PackageLinker（可选，用于深度追溯）

    Returns:
        C++ 父类名
    """
    parent_path = blueprint.parent_class
    if not parent_path:
        logger.warning("BlueprintMetadata.parent_class is None — using UObject as default")
        return "UObject"

    return ue_package_path_to_cpp_class(parent_path)


def _extract_component_properties(
    blueprint: "BlueprintMetadata",
    components: List[Dict]
) -> List[CppProperty]:
    """提取组件属性。

    从 blueprint.variables 中筛选 is_component=True 的变量，
    以及 result.components 列表中的 SCS 组件。

    Args:
        blueprint: BlueprintMetadata
        components: result.components 列表

    Returns:
        CppProperty 列表（category="component"）
    """
    properties: List[CppProperty] = []

    # 从 blueprint.variables 提取组件
    for var in blueprint.variables:
        if var.is_component:
            prop = _create_component_property(var)
            properties.append(prop)

    # 从 result.components 提取 SCS 组件（如果有）
    for comp in components:
        comp_name = comp.get("name", "")
        comp_class = comp.get("class", "")

        if comp_name and comp_class:
            # P1 改进：清理组件名称
            clean_name = _clean_component_name(comp_name)

            # 补全短名称为完整路径（如 "ArrowComponent" → "/Script/Engine.ArrowComponent"）
            comp_path = comp_class
            if not comp_path.startswith("/Script/"):
                # 假设是 Engine 类型，补全路径
                comp_path = f"/Script/Engine.{comp_class}"

            # 构建组件类型（指针）
            cpp_type = ue_path_to_cpp_type(comp_path)
            if not cpp_type.endswith("*"):
                cpp_type = f"{cpp_type}*"

            # SCS 组件默认标记
            marks = ["VisibleAnywhere", "BlueprintReadOnly", "Instanced"]

            prop = CppProperty(
                cpp_type=cpp_type,
                name=clean_name,
                uproperty_marks=marks,
                category="component",
                default_value=None,
            )
            properties.append(prop)

    return properties


def _create_component_property(var: "BlueprintVariable") -> CppProperty:
    """从 BlueprintVariable 创建组件 CppProperty。

    P1 改进：使用 _clean_component_name 清理组件名称。

    Args:
        var: BlueprintVariable（is_component=True）

    Returns:
        CppProperty
    """
    # P1 改进：清理组件名称
    clean_name = _clean_component_name(var.var_name)

    # 从 var_type 提取类型路径
    var_type = var.var_type
    ue_type = ""

    if var_type.pin_category == "object":
        # object 类型：pin_subcategory 是类名
        ue_type = var_type.pin_subcategory
        if not ue_type.startswith("/Script/"):
            # 补全路径
            ue_type = f"/Script/Engine.{ue_type}"
    else:
        # 其他类型直接使用 category
        ue_type = var_type.pin_category

    # 转换为 C++ 类型（组件是指针）
    cpp_type = ue_path_to_cpp_type(ue_type)
    if not cpp_type.endswith("*"):
        cpp_type = f"{cpp_type}*"

    # 获取 UPROPERTY 标记（组件模式）
    marks = cpf_flags_to_uproperty_marks(var.property_flags, is_component=True)

    return CppProperty(
        cpp_type=cpp_type,
        name=clean_name,
        uproperty_marks=marks,
        category="component",
        default_value=None,  # 组件无默认值
        cpp_comment=f"UE type: {ue_type}",
    )


def _extract_variable_properties(blueprint: "BlueprintMetadata") -> List[CppProperty]:
    """提取变量属性。

    从 blueprint.variables 中筛选 is_component=False 的变量。
    P0 改进：过滤蓝图内部元数据属性。

    Args:
        blueprint: BlueprintMetadata

    Returns:
        CppProperty 列表（category="variable"）
    """
    properties: List[CppProperty] = []

    for var in blueprint.variables:
        if not var.is_component:
            # P0 改进：过滤蓝图元数据
            if _is_blueprint_metadata(var.var_name):
                continue
            prop = _create_variable_property(var)
            properties.append(prop)

    return properties


def _extract_input_action_properties(graphs: List["UEdGraph"]) -> List[CppProperty]:
    """从图节点提取输入动作变量。

    P2 改进：从 K2Node_EnhancedInputAction 节点提取输入动作引用，
    生成 UInputAction* 成员变量。

    Args:
        graphs: 图列表

    Returns:
        CppProperty 列表（category="input"）
    """
    properties: List[CppProperty] = []
    seen_actions: set = set()

    for graph in graphs:
        for node in graph.nodes:
            if node.class_name != "K2Node_EnhancedInputAction":
                continue

            nd = node.node_data
            if not isinstance(nd, dict):
                continue

            # 获取输入动作引用
            action_path = nd.get("input_action_path", "")
            action_short_name = nd.get("input_action_short_name", "")

            if not action_path or action_path == "None":
                continue

            # 去重（同一个输入动作可能被多个节点引用）
            if action_path in seen_actions:
                continue
            seen_actions.add(action_path)

            # 生成变量名（使用短名称）
            var_name = action_short_name if action_short_name else action_path

            # 构建属性
            prop = CppProperty(
                cpp_type="UInputAction*",
                name=var_name,
                uproperty_marks=["EditAnywhere"],
                category="input",
                default_value=None,
                cpp_comment=f"Input Action: {action_path}",
            )
            properties.append(prop)

    return properties


def _create_variable_property(var: "BlueprintVariable") -> CppProperty:
    """从 BlueprintVariable 创建变量 CppProperty。

    Args:
        var: BlueprintVariable（is_component=False）

    Returns:
        CppProperty
    """
    var_type = var.var_type

    # 构建 UE 类型路径
    ue_type = _build_ue_type_from_pin_type(var_type)

    # 转换为 C++ 类型
    cpp_type = ue_path_to_cpp_type(ue_type)

    # 获取 UPROPERTY 标记（变量模式）
    marks = cpf_flags_to_uproperty_marks(var.property_flags, is_component=False)

    return CppProperty(
        cpp_type=cpp_type,
        name=sanitize_identifier(var.var_name),
        uproperty_marks=marks,
        category="variable",
        default_value=var.default_value,
        cpp_comment=f"UE type: {ue_type}",
    )


def _build_ue_type_from_pin_type(pin_type: "FEdGraphPinType") -> str:
    """从 FEdGraphPinType 构建 UE 类型路径。

    Args:
        pin_type: FEdGraphPinType

    Returns:
        UE 类型路径字符串
    """
    category = pin_type.pin_category
    subcategory = pin_type.pin_subcategory

    # 属性类型（Property）→ 映射到对应的 UE 基本类型
    if category in ("IntProperty",):
        return "int32"
    if category in ("FloatProperty", "DoubleProperty"):
        return "float" if category == "FloatProperty" else "double"
    if category in ("BoolProperty",):
        return "bool"
    if category in ("ObjectProperty", "SoftObjectProperty"):
        # ObjectProperty 总是指针类型
        cpp_type = subcategory if subcategory else "UObject"
        if not cpp_type.endswith("*"):
            cpp_type = f"{cpp_type}*"
        return cpp_type
    if category in ("ArrayProperty", "SetProperty", "MapProperty"):
        # 对于集合类型，返回元素类型（从 pin_type 中提取）
        # 如果没有 subcategory，返回基本类型
        return subcategory if subcategory else "FString"
    if category in ("StrProperty", "NameProperty", "TextProperty"):
        cpp_type_map = {
            "StrProperty": "FString",
            "NameProperty": "FName",
            "TextProperty": "FText",
        }
        return cpp_type_map.get(category, category)

    # 基本类型直接返回
    if category in ("float", "double", "bool", "int", "int32", "int64",
                     "byte", "string", "name", "text"):
        return category

    # object 类型：subcategory 是类名
    if category == "object":
        if subcategory:
            if subcategory.startswith("/Script/"):
                return subcategory
            # 补全路径
            return f"/Script/Engine.{subcategory}"
        return "UObject"  # 未知 object 类型

    # struct 类型：subcategory 是结构名
    if category in ("struct", "StructProperty"):
        if subcategory:
            if subcategory.startswith("/Script/"):
                return subcategory
            # 常见结构体补全路径
            common_structs = ("Vector", "Rotator", "Transform", "Vector2D",
                              "LinearColor", "Color", "Guid", "Quat", "Box")
            if subcategory in common_structs:
                return f"/Script/CoreUObject.{subcategory}"
            return f"/Script/CoreUObject.{subcategory}"
        # StructProperty 无 subcategory — 使用通用 FStruct 占位
        return "FStruct"

    # 其他类型返回 category
    return category


# ============================================================================
# 函数签名映射
# ============================================================================

# --- 辅助函数（Plan 02） ---

def _sanitize_identifier(name: str) -> str:
    """将 UE 引脚名转换为有效 C++ 标识符。

    委托给 sanitizer.sanitize_identifier。

    "Left / Right" → "Left__Right"
    "Primary Thumbstick" → "Primary_Thumbstick"
    "2DValue" → "_2DValue"
    "Target Touch UI" → "Target_Touch_UI"
    """
    return sanitize_identifier(name)


def _extract_cpp_type_from_pin(pin: "UEdGraphPin") -> Optional[str]:
    """将单个引脚转换为 C++ 类型字符串。

    返回 None 表示应跳过（exec/delegate 引脚）。
    """
    if pin.pin_type is None:
        return None
    pt = pin.pin_type
    if pt.pin_category in ("exec", "delegate"):
        return None

    # 获取基础类型
    if pt.pin_category in ("object", "struct"):
        # 尝试解析 pin_subcategory_object
        if pt.pin_subcategory_object and isinstance(pt.pin_subcategory_object, int):
            # 有 linker 时可解析，此处用 pin_subcategory 作为回退
            raw_path = pt.pin_subcategory
        else:
            raw_path = pt.pin_subcategory
        if not raw_path:
            raw_path = pt.pin_category
    else:
        raw_path = pt.pin_subcategory or pt.pin_category

    cpp_type = ue_path_to_cpp_type(raw_path)

    # 对象类型加指针
    if pt.pin_category == "object" and not cpp_type.endswith("*"):
        cpp_type = f"{cpp_type}*"

    # 方向修饰符
    if pt.is_reference and pt.is_const:
        cpp_type = f"const {cpp_type}&"
    elif pt.is_reference:
        cpp_type = f"{cpp_type}&"

    return cpp_type


def _extract_parameters_from_pins(
    pins: List["UEdGraphPin"],
    is_event: bool = False
) -> List[CppCallParameter]:
    """从引脚列表提取函数参数。"""
    params: List[CppCallParameter] = []
    for pin in pins:
        if pin.pin_type is None:
            continue
        pt = pin.pin_type
        # 跳过 exec / delegate
        if pt.pin_category in ("exec", "delegate"):
            continue
        # 跳过隐藏引脚
        if pin.hidden:
            continue
        # 事件节点跳过 OutputDelegate 和 then
        if is_event and pin.pin_name in ("OutputDelegate", "then"):
            continue

        cpp_type = _extract_cpp_type_from_pin(pin)
        if cpp_type is None:
            continue

        params.append(CppCallParameter(
            name=_sanitize_identifier(pin.pin_name),
            cpp_type=cpp_type,
            direction="input" if pin.direction == 0 else "output",
        ))
    return params


# ============================================================================
# 函数标志位常量（UE5 UFunctionFlags）- 参考 EFunctionFlags.cs
# ============================================================================

# 访问修饰符（这些标志不在 extra_flags 中，需要从其他来源推断）
FUNC_PUBLIC = 0x00000001  # 占位符，实际访问修饰符需要从其他信息推断
FUNC_PROTECTED = 0x00000002  # 占位符
FUNC_PRIVATE = 0x00000004  # 占位符

# 函数类型（参考 EFunctionFlags.cs）
FUNC_Final = 0x00000001
FUNC_RequiredAPI = 0x00000002
FUNC_BlueprintAuthorityOnly = 0x00000004
FUNC_BlueprintCosmetic = 0x00000008
FUNC_Net = 0x00000010
FUNC_NetReliable = 0x00000020
FUNC_Simulated = 0x00000040
FUNC_Exec = 0x00000100
FUNC_Native = 0x00000200
FUNC_Event = 0x00000400
FUNC_NetMulticast = 0x00000800
FUNC_UbergraphFunction = 0x00001000
FUNC_Static = 0x00002000
FUNC_MulticastDelegate = 0x00004000
FUNC_Delegate = 0x00008000
FUNC_HasDefaults = 0x00010000
FUNC_HasOutParms = 0x00020000
FUNC_BlueprintCallable = 0x00040000
FUNC_BlueprintPure = 0x00080000
FUNC_EditorOnly = 0x00100000
FUNC_Const = 0x00200000
FUNC_NetValidate = 0x00400000
FUNC_BlueprintEvent = 0x08000000


def _extractFunctionFlags(flags: int) -> Dict[str, bool]:
    """从 extra_flags 提取函数标志位。

    参考 EFunctionFlags.cs 的定义。

    Args:
        flags: extra_flags 值

    Returns:
        函数标志字典
    """
    return {
        # 访问修饰符（需要从其他信息推断）
        "is_public": False,  # 默认
        "is_protected": True,  # 默认
        "is_private": False,
        # 函数类型
        "is_blueprint_pure": bool(flags & FUNC_BlueprintPure),
        "is_blueprint_callable": bool(flags & FUNC_BlueprintCallable),
        "is_const": bool(flags & FUNC_Const),
        "is_static": bool(flags & FUNC_Static),
        "is_event": bool(flags & FUNC_Event),
        "is_blueprint_event": bool(flags & FUNC_BlueprintEvent),
        "is_final": bool(flags & FUNC_Final),
        "is_native": bool(flags & FUNC_Native),
    }


def _infer_ufunction_specifiers(
    pins: List["UEdGraphPin"],
    node_class_name: str,
    is_override: bool,
    extra_flags: int = 0
) -> List[str]:
    """推断 UFUNCTION 修饰符（D-57-03）。

    改进：从 extra_flags 提取标志位。
    """
    if is_override:
        return []

    # 从 extra_flags 提取标志
    flags = _extractFunctionFlags(extra_flags)

    # 如果 extra_flags 已经设置了 BlueprintPure/BlueprintCallable，直接使用
    if flags["is_blueprint_pure"]:
        return ["BlueprintPure"]
    if flags["is_blueprint_callable"]:
        return ["BlueprintCallable"]

    # 回退到从引脚推断
    has_exec_input = any(
        p for p in pins
        if p.pin_type and p.pin_type.pin_category == "exec" and p.direction == 0
    )
    has_exec_output = any(
        p for p in pins
        if p.pin_type and p.pin_type.pin_category == "exec" and p.direction == 1
    )
    if has_exec_input or has_exec_output:
        return ["BlueprintCallable"]
    return ["BlueprintPure"]


def _build_cpp_method_from_entry(
    fe_node: "K2NodeFunctionEntry",
    blueprint_functions: Dict
) -> CppMethodIR:
    """从 K2Node_FunctionEntry 构建 CppMethodIR。

    改进：从 extra_flags 提取函数标志。
    """
    # 从 node_data 获取 function_reference（可能在 node_data 字典中）
    func_ref = getattr(fe_node, 'function_reference', None)
    extra_flags = 0
    if fe_node.node_data:
        if isinstance(fe_node.node_data, dict):
            func_ref = fe_node.node_data.get('function_reference', func_ref)
            extra_flags = fe_node.node_data.get('extra_flags', 0)
        else:
            func_ref = getattr(fe_node.node_data, 'function_reference', func_ref)
            extra_flags = getattr(fe_node.node_data, 'extra_flags', 0)

    if func_ref is None:
        return None

    func_name = func_ref.member_name
    if not func_name or func_name == "None":
        return None

    # 提取函数标志
    flags = _extractFunctionFlags(extra_flags)

    # 双源交叉验证（D-57-01）
    bp_func = blueprint_functions.get(func_name)
    if bp_func:
        return_type = bp_func.return_type or "void"
        parameters = [
            CppCallParameter(
                name=_sanitize_identifier(p.name),
                cpp_type=ue_path_to_cpp_type(p.param_type),
                direction="input" if p.is_input else "output",
            )
            for p in bp_func.parameters
        ]
    else:
        # 从引脚回退
        parameters = _extract_parameters_from_pins(fe_node.pins)
        return_type = "void"

    specifiers = _infer_ufunction_specifiers(
        fe_node.pins,
        "K2Node_FunctionEntry",
        is_override=False,
        extra_flags=extra_flags
    )

    # 确定访问修饰符
    access_modifier = "protected"  # 默认
    if flags["is_public"]:
        access_modifier = "public"
    elif flags["is_private"]:
        access_modifier = "private"

    return CppMethodIR(
        cpp_name=_sanitize_identifier(func_name),
        return_type=return_type,
        parameters=parameters,
        ufunction_specifiers=specifiers,
        is_override=False,
        is_const=flags["is_const"],
        is_static=flags["is_static"],
        is_pure=flags["is_blueprint_pure"],
        is_event=flags["is_event"],
        is_native=flags["is_native"],
        access_modifier=access_modifier,
        source_node_type="K2Node_FunctionEntry",
    )


def _build_cpp_method_from_event(event_node: "K2NodeEvent") -> CppMethodIR:
    """从 K2Node_Event 构建 CppMethodIR（is_override=True）。"""
    # 从 node_data 获取 event_reference
    event_ref = None
    nd = event_node.node_data

    if nd is not None:
        if isinstance(nd, dict):
            # 字典格式：直接从字典获取
            event_ref = nd.get('event_reference')
        else:
            # 对象格式：使用 getattr
            event_ref = getattr(nd, 'event_reference', None)

    # 尝试从节点属性获取
    if event_ref is None:
        event_ref = getattr(event_node, 'event_reference', None)

    if event_ref is None:
        return None

    event_name = event_ref.member_name if hasattr(event_ref, 'member_name') else None
    if not event_name or event_name == "None":
        return None

    parameters = _extract_parameters_from_pins(event_node.pins, is_event=True)

    return CppMethodIR(
        cpp_name=_sanitize_identifier(event_name),
        return_type="void",
        parameters=parameters,
        ufunction_specifiers=[],
        is_override=True,
        source_node_type="K2Node_Event",
    )


# --- 主入口（Plan 02） ---

def extract_cpp_functions(
    graphs: List["UEdGraph"],
    blueprint_functions: Optional[List] = None,
    linker: Optional[Any] = None,
) -> List[CppMethodIR]:
    """从函数图节点提取 C++ 方法声明。

    遍历所有图，提取 K2Node_FunctionEntry 和 K2Node_Event(b_override_function=True)。
    """
    bp_lookup: Dict = {}
    if blueprint_functions:
        for func in blueprint_functions:
            bp_lookup[func.name] = func

    methods: List[CppMethodIR] = []
    for graph in graphs:
        for node in graph.nodes:
            if node.class_name == "K2Node_FunctionEntry":
                method = _build_cpp_method_from_entry(node, bp_lookup)
                if method:
                    methods.append(method)
            elif node.class_name == "K2Node_Event":
                # 检查 b_override_function（可能在 node_data 中）
                b_override = False
                nd = node.node_data
                if isinstance(nd, dict):
                    b_override = nd.get('b_override_function', False)
                else:
                    b_override = getattr(node, 'b_override_function', False)

                if b_override:
                    method = _build_cpp_method_from_event(node)
                    if method:
                        methods.append(method)
    return methods


# --- 调用语句提取（Plan 03） ---

def _derive_call_target(
    pins: List["UEdGraphPin"],
    b_self_context: bool
) -> Tuple[str, str]:
    """推导调用目标。

    b_self_context=True → ("this", "this")
    b_self_context=False → 从 self 引脚推导类型
    """
    if b_self_context:
        return ("this", "this")

    # 查找 self 引脚
    for pin in pins:
        if pin.pin_name == "self" and pin.pin_type:
            pt = pin.pin_type
            if pt.pin_category == "object":
                raw_path = pt.pin_subcategory
                if raw_path:
                    cpp_type = ue_path_to_cpp_type(raw_path)
                    return (cpp_type, "pointer")
    return ("Unknown", "pointer")


def extract_cpp_call_statements(
    graphs: List["UEdGraph"],
    linker: Optional[Any] = None,
) -> List[CppCallStatement]:
    """从 K2Node_CallFunction 节点提取 C++ 调用语句参考。"""
    statements: List[CppCallStatement] = []
    for graph in graphs:
        for node in graph.nodes:
            if node.class_name != "K2Node_CallFunction":
                continue

            # 获取 function_reference
            func_ref = getattr(node, 'function_reference', None)
            if func_ref is None:
                continue
            member_name = getattr(func_ref, 'member_name', None)
            if not member_name or member_name == "None":
                continue

            b_self_context = getattr(func_ref, 'b_self_context', True)
            target, target_type = _derive_call_target(node.pins, b_self_context)

            # 提取参数（跳过 exec/then/self）
            args = []
            for pin in node.pins:
                if pin.pin_type and pin.pin_type.pin_category == "exec":
                    continue
                if pin.pin_name in ("self", "then"):
                    continue
                args.append(_sanitize_identifier(pin.pin_name))

            statements.append(CppCallStatement(
                method_name=member_name,
                target=target,
                target_type=target_type,
                args=args,
                is_self_context=b_self_context,
            ))
    return statements


# ============================================================================
# 构造函数提取
# ============================================================================


def extract_cpp_constructor(ir: "CppClassIR") -> str:
    """从 CppClassIR 生成完整的 C++ 构造函数文本。

    便捷函数，调用 format_cpp_constructor 生成构造函数代码。

    Args:
        ir: CppClassIR 实例（constructor 字典已填充）

    Returns:
        完整的 C++ 构造函数文本
    """
    return format_cpp_constructor(ir)


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "extract_cpp_class_skeleton",
    "extract_cpp_functions",
    "extract_cpp_call_statements",
    "extract_cpp_constructor",
    "_sanitize_identifier",
    "_derive_call_target",
]