"""MaterialInstanceConstant 资产解析器。

解析 MaterialInstanceConstant 中的标量/向量/纹理参数覆盖。
包含边界检查和容错处理，避免异常数据导致整个解析失败。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 参数数量上限，防止异常数据导致无限循环或内存耗尽
MAX_PARAM_COUNT = 1000


def parse_material_instance(
    archive: Any,  # FArchive
    name_map: List[str],
) -> Dict[str, Any]:
    """解析 MaterialInstanceConstant 资产的核心属性。

    读取父材质索引、标量/向量/纹理参数覆盖列表。
    对每项计数进行边界检查，异常时记录警告并跳过对应段。
    任何未预期的异常被捕获并写入 result["parse_error"]，
    保证函数始终返回字典而非抛出异常。

    Args:
        archive: 已打开的 FArchive，当前位置应在数据区起始处
        name_map: 名称映射表，用于将 FName 索引转为字符串

    Returns:
        包含解析结果的字典，可能包含以下键:
        - parent_material_index: 父材质引用索引
        - scalar_overrides: 标量参数覆盖 {name: float}
        - vector_overrides: 向量参数覆盖 {name: (r, g, b, a)}
        - texture_overrides: 纹理参数覆盖 {name: int}
        - parameter_overrides: 合并的三类覆盖
        - override_count: 覆盖参数总数
        - parse_error: 解析失败时的错误信息
    """
    result: Dict[str, Any] = {}

    try:
        # 父材质索引
        parent_idx = archive.read_i32()
        result["parent_material_index"] = parent_idx

        # 标量参数覆盖
        scalar_count = archive.read_i32()
        if scalar_count < 0 or scalar_count > MAX_PARAM_COUNT:
            logger.warning(
                "Invalid scalar_count: %d, skipping scalar overrides",
                scalar_count,
            )
            scalar_count = 0

        scalar_overrides: Dict[str, float] = {}
        for _ in range(scalar_count):
            param_name_idx = archive.read_i32()
            if 0 <= param_name_idx < len(name_map):
                param_name = name_map[param_name_idx]
            else:
                param_name = f"param_{param_name_idx}"
            param_value = archive.read_f32()
            scalar_overrides[param_name] = param_value
        result["scalar_overrides"] = scalar_overrides

        # 向量参数覆盖
        vector_count = archive.read_i32()
        if vector_count < 0 or vector_count > MAX_PARAM_COUNT:
            logger.warning(
                "Invalid vector_count: %d, skipping vector overrides",
                vector_count,
            )
            vector_count = 0

        vector_overrides: Dict[str, tuple] = {}
        for _ in range(vector_count):
            param_name_idx = archive.read_i32()
            if 0 <= param_name_idx < len(name_map):
                param_name = name_map[param_name_idx]
            else:
                param_name = f"param_{param_name_idx}"
            r = archive.read_f32()
            g = archive.read_f32()
            b = archive.read_f32()
            a = archive.read_f32()
            vector_overrides[param_name] = (r, g, b, a)
        result["vector_overrides"] = vector_overrides

        # 纹理参数覆盖
        texture_count = archive.read_i32()
        if texture_count < 0 or texture_count > MAX_PARAM_COUNT:
            logger.warning(
                "Invalid texture_count: %d, skipping texture overrides",
                texture_count,
            )
            texture_count = 0

        texture_overrides: Dict[str, int] = {}
        for _ in range(texture_count):
            param_name_idx = archive.read_i32()
            if 0 <= param_name_idx < len(name_map):
                param_name = name_map[param_name_idx]
            else:
                param_name = f"param_{param_name_idx}"
            texture_idx = archive.read_i32()
            texture_overrides[param_name] = texture_idx
        result["texture_overrides"] = texture_overrides

        # 合并输出
        result["parameter_overrides"] = {
            "scalar": scalar_overrides,
            "vector": vector_overrides,
            "texture": texture_overrides,
        }
        result["override_count"] = scalar_count + vector_count + texture_count

    except Exception as e:
        logger.error("MaterialInstance parse failed: %s", e)
        result["parse_error"] = str(e)

    return result
