"""
C++ JSON IR 格式化模块 — CppProperty, CppHeaderMeta, CppClassIR 数据模型。

Per D-06: JSON IR 结构包含 header_meta, properties, methods, constructor 四部分。
Phase 56: 只填充 header_meta 和 properties，methods 和 constructor 留空。

导出：
    CppProperty: 单个 C++ UPROPERTY 声明数据模型
    CppHeaderMeta: 头文件元数据模型
    CppClassIR: 完整 C++ 类骨架 IR 数据模型
    format_cpp_class_json: JSON IR 格式化函数
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import logging

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


# ============================================================================
# C++ 类骨架 IR 数据模型（Per D-01, D-06）
# ============================================================================

@dataclass
class CppClassIR:
    """完整 C++ 类骨架 IR（D-01, D-06）。

    Phase 56: 只填充 name, parent_class, header_meta, properties。
    Phase 57-59: 分别填充 methods 和 constructor。

    Attributes:
        name: C++ 类名（如 "ABP_FirstPersonCharacter"）
        parent_class: 父类名（如 "ACharacter"）
        header_meta: 头文件元数据
        properties: 属性列表（组件 + 变量）
        methods: 方法列表（Phase 57 填充，Phase 56 为空）
        constructor: 构造函数数据（Phase 59 填充，Phase 56 为空字典）
    """
    name: str
    parent_class: str
    header_meta: CppHeaderMeta = field(default_factory=CppHeaderMeta)
    properties: List[CppProperty] = field(default_factory=list)
    methods: List[Any] = field(default_factory=list)  # Phase 57 填充
    constructor: Dict[str, List] = field(default_factory=lambda: {
        "component_creations": [],
        "component_assignments": [],
        "default_values": [],
    })  # Phase 59 填充

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
            "methods": self.methods,  # 空列表（Phase 56）
            "constructor": self.constructor,  # 空字典（Phase 56）
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
]