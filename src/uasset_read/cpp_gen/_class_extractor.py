"""C++ 类骨架提取 — 类名/父类解析。"""
from __future__ import annotations

import re
import logging
from typing import TYPE_CHECKING, Optional, Any

from uasset_read.cpp_gen.cpp_type_mapper import (
    ue_package_path_to_cpp_class,
    infer_class_prefix,
)

if TYPE_CHECKING:
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.models.blueprint import BlueprintMetadata

logger = logging.getLogger(__name__)

# ============================================================================
# 继承链深度限制（T-056-03）
# ============================================================================

MAX_INHERITANCE_DEPTH = 50  # 防止无限循环


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
# 类名/父类提取
# ============================================================================

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
