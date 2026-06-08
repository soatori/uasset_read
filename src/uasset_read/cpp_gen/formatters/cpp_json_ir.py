"""
C++ JSON IR 格式化模块 — CppProperty, CppHeaderMeta, CppClassIR, CppStatement 数据模型。

Per D-06: JSON IR 结构包含 header_meta, properties, methods, constructor 四部分。
只填充 header_meta 和 properties，methods 和 constructor 留空。

导出：
    CppProperty: 单个 C++ UPROPERTY 声明数据模型
    CppHeaderMeta: 头文件元数据模型
    CppClassIR: 完整 C++ 类骨架 IR 数据模型
    format_cpp_class_json: JSON IR 格式化函数
    kismet_to_cpp_body: Kismet 表达式 → 结构化 C++ 语句列表
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import logging

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.kismet.translator import KismetTranslator

logger = logging.getLogger(__name__)


# ============================================================================
# C++ 属性数据模型（Per D-06）
# ============================================================================

@dataclass
class CppProperty:
    """单个 C++ UPROPERTY 声明。

    用于表示蓝图变量或组件的 C++ 属性声明。

    Attributes:
        cpp_type: C++ 类型名（如 "USceneComponent*", "FVector", "float")
        name: 属性名（如 "DefaultSceneRoot", "MoveSpeed")
        uproperty_marks: UPROPERTY 标记列表（如 ["VisibleAnywhere", "BlueprintReadOnly", "Instanced"]）
        category: 属性类别（"component" 或 "variable"）
        default_value: 默认值（组件为 None，float 变量可能是 100.0）
        cpp_comment: 可选注释（原 UE 类型参考）
    """
    cpp_type: str
    name: str
    uproperty_marks: List[str]
    category: str  # "component" 或 "variable"
    default_value: Any = None
    cpp_comment: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 兼容字典（D-06 格式）。

        Returns:
            包含所有字段的字典，default_value 保留原值（None → JSON null）
        """
        result = {
            "cpp_type": self.cpp_type,
            "name": self.name,
            "uproperty_marks": self.uproperty_marks,
            "category": self.category,
            "default_value": self.default_value,
        }
        if self.cpp_comment:
            result["cpp_comment"] = self.cpp_comment
        return result


# ============================================================================
# C++ 头文件元数据模型（Per D-05, D-06）
# ============================================================================

@dataclass
class CppHeaderMeta:
    """头文件元数据。

    Per D-05: 完整 UE 头文件模板结构。

    Attributes:
        pragma_once: 是否包含 #pragma once（默认 True）
        includes: 包含的头文件列表（如 '"Engine/GameFramework/Character.h"'）
        forward_declarations: 前向声明列表
        generated_include: .generated.h 包含路径（必须为最后一个 include）
    """
    pragma_once: bool = True
    includes: List[str] = field(default_factory=list)
    forward_declarations: List[str] = field(default_factory=list)
    generated_include: str = ""

    @classmethod
    def build_from_parent(cls, parent_class: str, class_name: str) -> "CppHeaderMeta":
        """根据父类构建头文件元数据。

        Per D-05: 设置 generated_include 为 '{class_name}.generated.h'。
        根据父类类型添加对应的头文件包含。

        Args:
            parent_class: 父类 C++ 名（如 "ACharacter", "UActorComponent"）
            class_name: 当前类名（用于生成 .generated.h 路径）

        Returns:
            配置好的 CppHeaderMeta 实例
        """
        # T-056-04: 清理类名 — 只允许字母数字和下划线
        if class_name:
            import re
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', class_name):
                logger.warning(f"Invalid class name format: '{class_name}', sanitizing")
                # 移除非法字符
                class_name = re.sub(r'[^A-Za-z0-9_]', '_', class_name)

        meta = cls(
            pragma_once=True,
            includes=[],
            forward_declarations=[],
            generated_include=f'"{class_name}.generated.h"' if class_name else ""
        )

        # 根据父类前缀推断头文件路径
        if parent_class:
            # 提取类名部分（去掉前缀）
            base_name = parent_class
            if parent_class.startswith(('A', 'U', 'F', 'E', 'I')):
                base_name = parent_class[1:]

            # Actor 类使用 GameFramework 路径
            if parent_class.startswith('A'):
                meta.includes.append(f'"Engine/GameFramework/{base_name}.h"')
            # Component 类使用 Components 路径
            elif parent_class.startswith('U') and base_name.endswith('Component'):
                meta.includes.append(f'"Components/{base_name}.h"')
            # 其他 UObject 派生类
            elif parent_class.startswith('U'):
                meta.includes.append(f'"Engine/{base_name}.h"')
            # 结构体
            elif parent_class.startswith('F'):
                # 核心结构体在 CoreUObject
                if base_name in ('Vector', 'Rotator', 'Transform', 'Vector2D',
                                  'LinearColor', 'Color', 'Guid', 'Quat', 'Plane', 'Box'):
                    meta.includes.append('"CoreUObject.h"')
                else:
                    meta.includes.append(f'"Engine/{base_name}.h"')

        return meta

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 兼容字典（D-06 格式）。"""
        return {
            "pragma_once": self.pragma_once,
            "includes": self.includes,
            "forward_declarations": self.forward_declarations,
            "generated_include": self.generated_include,
        }


@dataclass
class CppCallParameter:
    """函数/调用中的单个参数。

    Attributes:
        name:  sanitized C++ 标识符（如 "LeftRight"）
        cpp_type: C++ 类型（含方向修饰，如 "const FString&", "double"）
        direction: "input" | "output" | "return"
    """
    name: str
    cpp_type: str
    direction: str  # "input" | "output" | "return"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cpp_type": self.cpp_type,
            "direction": self.direction,
        }


@dataclass
class CppMethodIR:
    """蓝图函数 → C++ 方法声明（D-57-02）。

    Attributes:
        cpp_name: C++ 函数名（已清理，如 "PrimaryThumbstick"）
        return_type: C++ 返回类型（默认 "void"）
        parameters: 参数列表
        ufunction_specifiers: UFUNCTION 宏标记（如 ["BlueprintCallable"]）
        is_override: True 表示 K2Node_Event 的 bOverrideFunction
        is_const: const 方法修饰符（默认 False）
        is_static: static 方法修饰符
        is_virtual: virtual 方法修饰符
        is_pure: 纯函数（无副作用）
        is_event: 事件函数
        is_native: 原生函数
        access_modifier: 访问修饰符（"public"、"protected"、"private"）
        source_node_type: "K2Node_FunctionEntry" | "K2Node_Event" | ""
        body: 函数体语句（结构化 IR）
        body_text: Kismet 反编译函数体文本（原始 C++ 伪代码）
    """
    cpp_name: str
    return_type: str
    parameters: List[CppCallParameter]
    ufunction_specifiers: List[str]
    is_override: bool
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_pure: bool = False
    is_event: bool = False
    is_native: bool = False
    access_modifier: str = "protected"  # 默认 protected
    source_node_type: str = ""
    class_name: str = ""  # 所属类名（用于 .cpp 实现中 ClassName::Method 前缀）
    body: List["CppStatement"] = field(default_factory=list)  # 函数体语句
    body_text: Optional[str] = None  # Kismet 反编译函数体文本 (D-66-03)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "cpp_name": self.cpp_name,
            "return_type": self.return_type,
            "parameters": [p.to_dict() for p in self.parameters],
            "ufunction_specifiers": self.ufunction_specifiers,
            "is_override": self.is_override,
            "is_const": self.is_const,
            "is_static": self.is_static,
            "is_virtual": self.is_virtual,
            "is_pure": self.is_pure,
            "is_event": self.is_event,
            "is_native": self.is_native,
            "access_modifier": self.access_modifier,
            "source_node_type": self.source_node_type,
            "body": [s.to_dict() for s in self.body],
        }
        if self.class_name:
            result["class_name"] = self.class_name
        if self.body_text is not None:
            result["body_text"] = self.body_text
        return result


@dataclass
class CppCallStatement:
    """K2Node_CallFunction → C++ 调用语句参考（D-57-02）。

    Attributes:
        method_name: 被调用的方法名
        target: 调用目标（"this" 或变量名）
        target_type: "this" | "pointer"（控制 -> 访问符）
        args: 参数名列表（已清理的标识符）
        is_self_context: 来自 FMemberReference.b_self_context
    """
    method_name: str
    target: str
    target_type: str = "pointer"
    args: List[str] = field(default_factory=list)
    is_self_context: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method_name": self.method_name,
            "target": self.target,
            "target_type": self.target_type,
            "args": self.args,
            "is_self_context": self.is_self_context,
        }


@dataclass
class CppStatement:
    """C++ 语句基类。

    所有具体语句类型继承此类，用于表示函数体中的单条 C++ 语句。
    """
    statement_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"statement_type": self.statement_type}


@dataclass
class CppCallStmt(CppStatement):
    """函数调用语句。

    Attributes:
        target: 调用目标对象（"Super", "this", 或变量名）
        method_name: 方法名
        args: 参数列表（字符串）
        is_pure: 是否为 pure 函数调用
    """
    target: str = ""
    method_name: str = ""
    args: List[str] = field(default_factory=list)
    is_pure: bool = False
    statement_type: str = "call"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "target": self.target,
            "method_name": self.method_name,
            "args": self.args,
            "is_pure": self.is_pure,
        }


@dataclass
class CppAssignmentStmt(CppStatement):
    """赋值语句：lhs = rhs;

    Attributes:
        lhs: 左值变量名
        rhs: 右值表达式
        cpp_type: C++ 类型
    """
    lhs: str = ""
    rhs: str = ""
    cpp_type: str = ""
    statement_type: str = "assignment"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "lhs": self.lhs,
            "rhs": self.rhs,
            "cpp_type": self.cpp_type,
        }


@dataclass
class CppIfStmt(CppStatement):
    """条件语句：if (condition) { then_body } [else { else_body }]

    Attributes:
        condition: 条件表达式
        then_body: then 分支语句列表
        else_body: else 分支语句列表（可为空）
    """
    condition: str = ""
    then_body: List["CppStatement"] = field(default_factory=list)
    else_body: List["CppStatement"] = field(default_factory=list)
    statement_type: str = "if"

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "statement_type": self.statement_type,
            "condition": self.condition,
            "then_body": [s.to_dict() for s in self.then_body],
        }
        if self.else_body:
            result["else_body"] = [s.to_dict() for s in self.else_body]
        return result


@dataclass
class CppInlineExprStmt(CppStatement):
    """内联表达式语句（不独立成行，仅嵌入到其他语句参数中）。

    Attributes:
        expression: 内联表达式文本
    """
    expression: str = ""
    statement_type: str = "inline_expr"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "expression": self.expression,
        }


@dataclass
class CppReturnStmt(CppStatement):
    """return 语句。

    Attributes:
        value: 返回值表达式（空字符串表示无返回值的 return）
    """
    value: str = ""
    statement_type: str = "return"

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"statement_type": self.statement_type}
        if self.value:
            result["value"] = self.value
        return result


@dataclass
class CppWhileStmt(CppStatement):
    """while 循环语句。

    Attributes:
        condition: 循环条件表达式
    """
    condition: str = ""
    statement_type: str = "while"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "condition": self.condition,
        }


@dataclass
class CppForStmt(CppStatement):
    """for 循环语句：for (init; condition; increment) { body }

    Attributes:
        init: 初始化表达式
        condition: 循环条件
        increment: 递增表达式
        body: 循环体语句列表
    """
    init: str = ""
    condition: str = ""
    increment: str = ""
    body: List["CppStatement"] = field(default_factory=list)
    statement_type: str = "for"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "init": self.init,
            "condition": self.condition,
            "increment": self.increment,
            "body": [s.to_dict() for s in self.body],
        }


@dataclass
class CppForEachStmt(CppStatement):
    """range-based for 循环：for (auto& elem : container) { body }

    Attributes:
        element: 循环变量名
        element_type: 元素类型（默认 "auto&"）
        container: 容器表达式
        body: 循环体语句列表
    """
    element: str = ""
    element_type: str = "auto&"
    container: str = ""
    body: List["CppStatement"] = field(default_factory=list)
    statement_type: str = "for_each"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "element": self.element,
            "element_type": self.element_type,
            "container": self.container,
            "body": [s.to_dict() for s in self.body],
        }


@dataclass
class CppRawStmt(CppStatement):
    """未分类的原始 C++ 文本语句。

    用于无法归入其他具体类型的文本输出（如 goto、switch、注释等）。

    Attributes:
        raw_text: 原始 C++ 文本
    """
    raw_text: str = ""
    statement_type: str = "raw"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "raw_text": self.raw_text,
        }


# ============================================================================
# Kismet 表达式 → 结构化 C++ 语句分类器
# ============================================================================

# 分类优先级顺序：从最具体到最通用
# 每个模式元组: (compiled_regex, factory_function)
_IF_PATTERN = re.compile(r'^if\s*\((.+)\)\s*\{?$')
_WHILE_PATTERN = re.compile(r'^while\s*\((.+)\)\s*\{?$')
_RETURN_PATTERN = re.compile(r'^return(?:\s+(.+))?$')
_ASSIGN_PATTERN = re.compile(r'^([\w][\w.>-]*)\s*=\s*(.+)$')
_CALL_PATTERN = re.compile(r'^([\w][\w:>-]*)\((.*)\)$')
_GOTO_PATTERN = re.compile(r'^goto\s+(\w+);?$')


def _classify_cpp_line(line: str) -> CppStatement:
    """将单行 C++ 文本分类为结构化语句。

    分类规则（按优先级）:
    1. if (cond) {  → CppIfStmt
    2. while (cond) { → CppWhileStmt
    3. return [expr] → CppReturnStmt
    4. lhs = rhs → CppAssignmentStmt
    5. func(args) / Class::Func(args) → CppCallStmt
    6. goto Label_N → CppRawStmt
    7. 其他 → CppRawStmt

    Args:
        line: 单行 C++ 文本（已 strip）

    Returns:
        分类后的 CppStatement 实例
    """
    # 1. if 语句
    m = _IF_PATTERN.match(line)
    if m:
        return CppIfStmt(condition=m.group(1))

    # 2. while 语句
    m = _WHILE_PATTERN.match(line)
    if m:
        return CppWhileStmt(condition=m.group(1))

    # 3. return 语句
    m = _RETURN_PATTERN.match(line)
    if m:
        return CppReturnStmt(value=m.group(1) or "")

    # 4. 赋值语句: lhs = rhs
    #    仅当行中存在顶层 = 且左侧不是函数名时分类为赋值
    m = _ASSIGN_PATTERN.match(line)
    if m:
        lhs = m.group(1)
        rhs = m.group(2)
        # 排除误匹配：如果左侧包含 :: 或 -> 后紧跟 (，则是调用不是赋值
        # 例如 "Obj->Func()" 不应匹配为赋值
        if '(' not in lhs and not rhs.lstrip().startswith('('):
            return CppAssignmentStmt(lhs=lhs, rhs=rhs)

    # 5. 函数调用: Func(args) 或 Class::Func(args)
    m = _CALL_PATTERN.match(line)
    if m:
        method_name = m.group(1)
        args_str = m.group(2).strip()
        args = _split_args(args_str) if args_str else []
        return CppCallStmt(method_name=method_name, args=args)

    # 6. 其他: goto、switch、注释等统一归为 CppRawStmt
    return CppRawStmt(raw_text=line)


def _split_args(args_str: str) -> List[str]:
    """安全分割函数参数字符串（处理嵌套括号）。

    Args:
        args_str: 逗号分隔的参数字符串

    Returns:
        参数列表
    """
    if not args_str:
        return []

    result: List[str] = []
    depth = 0
    current: List[str] = []

    for ch in args_str:
        if ch in ('(', '<', '[', '{'):
            depth += 1
            current.append(ch)
        elif ch in (')', '>', ']', '}'):
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)

    if current:
        result.append(''.join(current).strip())

    return result


def kismet_to_cpp_body(
    expressions: List["KismetExpression"],
    translator: "KismetTranslator",
) -> List[CppStatement]:
    """将 Kismet 表达式列表转换为结构化 C++ 语句列表。

    遍历每个表达式，调用 translator.line_cpp() 获取 C++ 文本，
    然后将文本分类为 CppCallStmt、CppAssignmentStmt、CppIfStmt 等。

    Args:
        expressions: Kismet 表达式列表（来自字节码解析）
        translator: KismetTranslator 实例（含 JumpAnalyzer 结构化检测）

    Returns:
        结构化 CppStatement 列表
    """
    statements: List[CppStatement] = []

    for idx, expr in enumerate(expressions):
        text = translator.line_cpp(expr, index=idx)
        if not text or not text.strip():
            continue

        # 处理多行输出（如 EX_SwitchValue 产生的 switch/case）
        lines = text.split("\n")
        for sub_line in lines:
            sub_line = sub_line.strip()
            if not sub_line:
                continue
            stmt = _classify_cpp_line(sub_line)
            statements.append(stmt)

    return statements

# ============================================================================
# C++ 类骨架 IR 数据模型（Per D-01, D-06）
# ============================================================================

@dataclass
class CppClassIR:
    """完整 C++ 类骨架 IR（D-01, D-06）。

    Attributes:
        name: C++ 类名（如 "ABP_FirstPersonCharacter"）
        parent_class: 父类名（如 "ACharacter"）
        header_meta: 头文件元数据
        properties: 属性列表（组件 + 变量）
        methods: 方法列表（填充后可用）
        constructor: 构造函数数据（填充后可用）
    """
    name: str
    parent_class: str
    header_meta: CppHeaderMeta = field(default_factory=CppHeaderMeta)
    properties: List[CppProperty] = field(default_factory=list)
    methods: List["CppMethodIR"] = field(default_factory=list)
    constructor: Dict[str, List] = field(default_factory=lambda: {
        "component_creations": [],
        "component_assignments": [],
        "default_values": [],
    })  # 填充

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 兼容字典（D-06 格式）。

        输出结构：
        {
            "name": "...",
            "parent_class": "...",
            "header_meta": {...},
            "properties": [...],
            "methods": [],
            "constructor": {"component_creations": [], ...}
        }

        Returns:
            JSON 兼容的字典结构
        """
        return {
            "name": self.name,
            "parent_class": self.parent_class,
            "header_meta": self.header_meta.to_dict(),
            "properties": [prop.to_dict() for prop in self.properties],
            "methods": [m.to_dict() if hasattr(m, "to_dict") else m for m in self.methods],
            "constructor": self.constructor,  # 空字典
        }


# ============================================================================
# JSON IR 格式化函数
# ============================================================================

def format_cpp_class_json(ir: CppClassIR, output_version: str = "1.0") -> Dict[str, Any]:
    """格式化 CppClassIR 为 JSON IR 输出（D-06）。

    输出结构：
    {
        "cpp_class": {
            "name": "...",
            "parent_class": "...",
            "header_meta": {...},
            "properties": [...],
            "methods": [],
            "constructor": {...}
        },
        "output_version": "1.0"
    }

    Args:
        ir: CppClassIR 数据模型
        output_version: 输出版本号（默认 "1.0"）

    Returns:
        包含 cpp_class 和 output_version 的字典
    """
    return {
        "cpp_class": ir.to_dict(),
        "output_version": output_version,
    }


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
    # Method/Call IR
    "CppCallParameter",
    "CppMethodIR",
    "CppCallStatement",
    # Statement IR
    "CppStatement",
    "CppCallStmt",
    "CppAssignmentStmt",
    "CppIfStmt",
    "CppInlineExprStmt",
    "CppReturnStmt",
    "CppWhileStmt",
    "CppRawStmt",
    # Body builder
    "kismet_to_cpp_body",
]