"""C++ 构造函数文本格式化器。

将 CppClassIR.constructor 字典中的 IR 数据格式化为完整的 C++ 构造函数文本。

函数：
    build_constructor_sections: 将 constructor IR 分类为 5 个代码段
    format_cpp_constructor: 组装完整构造函数文本

安全缓解（威胁模型）：
    T-059-05: 字符串值传入 TEXT() 时转义引号和反斜杠
    T-059-06: 组件创建按拓扑排序排列（基于 attach 关系）
    T-059-07: InputAction asset_path 验证 /Game/... 模式
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from uasset_read.cpp_gen.cpp_constructor_ir_builder import (
    CppComponentAssignment,
    CppComponentCreation,
    CppDefaultValue,
)
from uasset_read.cpp_gen.cpp_default_value_formatter import (
    _escape_cpp_string,
    format_cpp_default_value,
    format_cpp_input_action_load,
    format_cpp_transform,
)
from uasset_read.models.transforms import RotatorValue, VectorValue

if TYPE_CHECKING:
    from uasset_read.cpp_gen.formatters.cpp_json_ir import CppClassIR

# ============================================================================
# 常量
# ============================================================================

_SECTION_COMMENTS = {
    "creation": "// Component creation",
    "attach": "// Setup attachments",
    "transform": "// Transform assignments",
    "property": "// Property assignments",
    "load_object": "// InputAction loads",
}

_SECTION_ORDER = ["creation", "attach", "transform", "property", "load_object"]

_INDENT = "    "  # 4-space indent


# ============================================================================
# 拓扑排序（T-059-06）
# ============================================================================


def _topological_sort_creations(
    creations: List[CppComponentCreation],
    assignments: List[CppComponentAssignment],
) -> List[CppComponentCreation]:
    """按拓扑排序排列组件创建顺序（T-059-06）。

    基于 attach 关系：被 attach 的组件（parent_name）必须先创建。

    Args:
        creations: 原始组件创建列表
        assignments: attach 关系列表

    Returns:
        拓扑排序后的组件创建列表
    """
    if not creations:
        return []

    # 构建组件名到 creation 的映射
    name_to_creation = {c.variable_name: c for c in creations}
    all_names = set(name_to_creation.keys())

    # 构建依赖图：child 依赖 parent（parent 必须先创建）
    # 注意：assignments 中的 parent_name 可能不是 components（如 RootComponent）
    # 只关注都在 creations 中的组件
    dependencies: Dict[str, set] = {name: set() for name in all_names}
    for assign in assignments:
        child = assign.child_name
        parent = assign.parent_name
        if child in all_names and parent in all_names:
            dependencies[child].add(parent)

    # Kahn's algorithm
    in_degree = {name: len(deps) for name, deps in dependencies.items()}
    queue = [name for name, deg in in_degree.items() if deg == 0]
    queue.sort()  # 稳定排序
    result: List[CppComponentCreation] = []

    while queue:
        node = queue.pop(0)
        result.append(name_to_creation[node])
        for name, deps in dependencies.items():
            if node in deps:
                deps.discard(node)
                in_degree[name] -= 1
                if in_degree[name] == 0:
                    queue.append(name)
                    queue.sort()

    # 如果有循环依赖，剩余组件按原始顺序追加
    if len(result) < len(creations):
        seen = {c.variable_name for c in result}
        for c in creations:
            if c.variable_name not in seen:
                result.append(c)

    return result


# ============================================================================
# build_constructor_sections
# ============================================================================


def _normalize_transform_keys(transforms: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize transform key names and value types for format_cpp_transform.

    - Renames 'relative_scale3d' → 'relative_scale' (key mismatch fix)
    - Converts dict-based location/rotation to VectorValue/RotatorValue objects
      (build_transform_assignments stores raw dicts, format_cpp_transform expects
      typed value objects).
    """
    result = dict(transforms)
    if "relative_scale3d" in result and "relative_scale" not in result:
        result["relative_scale"] = result.pop("relative_scale3d")

    # Convert dict-based location to VectorValue
    loc = result.get("relative_location")
    if isinstance(loc, dict) and not isinstance(loc, VectorValue):
        result["relative_location"] = VectorValue(
            x=loc.get("X", 0.0),
            y=loc.get("Y", 0.0),
            z=loc.get("Z", 0.0),
        )

    # Convert dict-based rotation to RotatorValue
    rot = result.get("relative_rotation")
    if isinstance(rot, dict) and not isinstance(rot, RotatorValue):
        result["relative_rotation"] = RotatorValue(
            roll=rot.get("Roll", 0.0),
            pitch=rot.get("Pitch", 0.0),
            yaw=rot.get("Yaw", 0.0),
        )

    return result


def build_constructor_sections(ir: "CppClassIR") -> Dict[str, List[str]]:
    """将 constructor 字典中的三个列表分类为有注释的代码段。

    分类逻辑：
    1. creation: 从 component_creations 生成 CreateDefaultSubobject 调用
    2. attach: 从 component_assignments 生成 SetupAttachment 调用
    3. transform: 从 default_values 筛选 is_method_call=True, method_type="transform"
    4. property: 从 default_values 筛选普通属性赋值
    5. load_object: 从 default_values 筛选 needs_load_object=True

    组件创建顺序按拓扑排序排列（T-059-06）。

    Args:
        ir: CppClassIR 实例，其 constructor 字典已填充

    Returns:
        包含 5 个代码段的字典，每段为代码行字符串列表
    """
    constructor = ir.constructor
    creations: List[CppComponentCreation] = constructor.get("component_creations", [])
    assignments: List[CppComponentAssignment] = constructor.get("component_assignments", [])
    default_values: List[CppDefaultValue] = constructor.get("default_values", [])

    sections: Dict[str, List[str]] = {
        "creation": [],
        "attach": [],
        "transform": [],
        "property": [],
        "load_object": [],
    }

    # 1. creation 段 — 拓扑排序（T-059-06）
    sorted_creations = _topological_sort_creations(creations, assignments)
    for creation in sorted_creations:
        line = (
            f"{creation.variable_name} = "
            f"CreateDefaultSubobject<{creation.cpp_type}>"
            f'(TEXT("{creation.component_name}"));'
        )
        sections["creation"].append(line)

    # 2. attach 段
    for assign in assignments:
        if assign.socket_name:
            line = (
                f"{assign.child_name}->SetupAttachment("
                f"{assign.parent_name}, FName(\"{assign.socket_name}\"));"
            )
        else:
            line = f"{assign.child_name}->SetupAttachment({assign.parent_name});"
        sections["attach"].append(line)

    # 3. transform 段 — 从 default_values 筛选 is_method_call=True, method_type="transform"
    # 4. property 段 — 从 default_values 筛选普通属性赋值
    # 5. load_object 段 — 从 default_values 筛选 needs_load_object=True
    for entry in default_values:
        # T-059-07: InputAction LoadObject
        if entry.needs_load_object:
            try:
                load_line = format_cpp_input_action_load(entry.target, entry.value)
                if load_line:
                    sections["load_object"].append(load_line)
            except ValueError as e:
                # 路径验证失败 — 记录警告并跳过
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Skipping LoadObject for '{entry.target}': {e}"
                )
            continue

        # Transform 方法调用
        if entry.is_method_call and entry.method_type == "transform":
            # Normalize scale key for format_cpp_transform compatibility
            normalized_value = _normalize_transform_keys(entry.value)
            transform_lines = format_cpp_transform(normalized_value, entry.target)
            sections["transform"].extend(transform_lines)
            continue

        # 普通属性赋值（排除方法调用和 LoadObject）
        if not entry.is_method_call and not entry.needs_load_object:
            cpp_value = format_cpp_default_value(entry.value, entry.cpp_type)
            if cpp_value:
                sections["property"].append(f"{entry.target} = {cpp_value};")

    return sections


# ============================================================================
# format_cpp_constructor
# ============================================================================


def format_cpp_constructor(ir: "CppClassIR") -> str:
    """组装完整 C++ 构造函数文本。

    输出格式：
    ```cpp
    ClassName::ClassName()
        : Super::ParentClass()
    {
        // Component creation
        ...

        // Setup attachments
        ...

        // Transform assignments
        ...

        // Property assignments
        ...

        // InputAction loads
        ...
    }
    ```

    - 函数签名：ClassName::ClassName()
    - 初始化列表：Super::ClassName()（无条件，D-59-05）
    - 每段之间空一行
    - 空段被跳过
    - 4 空格缩进

    Args:
        ir: CppClassIR 实例

    Returns:
        完整的 C++ 构造函数文本
    """
    sections = build_constructor_sections(ir)

    lines: List[str] = []

    # 函数签名
    lines.append(f"{ir.name}::{ir.name}()")

    # 初始化列表 — UE5 使用 Super() 作为父类构造调用
    lines.append(f"    : Super()")

    # 函数体开始
    lines.append("{")

    # 按顺序输出各段（跳过空段）
    first_section = True
    for section_key in _SECTION_ORDER:
        section_lines = sections.get(section_key, [])
        if not section_lines:
            continue

        # 段之间空一行
        if not first_section:
            lines.append("")
        first_section = False

        # 段注释
        lines.append(f"{_INDENT}{_SECTION_COMMENTS[section_key]}")

        # 段内代码
        for code_line in section_lines:
            # 多行语句（如 transform 的多行调用）需要逐行缩进
            code_lines = code_line.split("\n")
            for i, cl in enumerate(code_lines):
                if i == 0:
                    lines.append(f"{_INDENT}{cl}")
                else:
                    lines.append(f"{_INDENT}{cl}")

    # 函数体结束
    lines.append("}")

    return "\n".join(lines)


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "build_constructor_sections",
    "format_cpp_constructor",
]
