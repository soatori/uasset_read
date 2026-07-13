"""动画解析共享模块

提取自 anim_blueprint.py / anim_montage.py / anim_sequence.py 的重复逻辑：
- parse_anim_notifies: 动画通知数组解析
- parse_float_curve_names: 浮点曲线名称解析
- ensure_custom_data: export.custom_data 初始化
"""

from typing import Any

from uasset_read.models.ir import AnimNotifyIR
from uasset_read.parsers.asset_types.property_extractor import (
    extract_object_ref,
    parse_dict_list,
)


def parse_anim_notifies(data: Any) -> list[AnimNotifyIR]:
    """解析动画通知数组（完整字段版本）

    提取所有 AnimNotifyIR 字段，包括 LinkedMontage / LinkedSequence 对象引用。
    三个动画解析器共享此实现。
    """

    def _parse_notify(notify_data: dict) -> AnimNotifyIR:
        notify = AnimNotifyIR(
            notify_name=notify_data.get("NotifyName", ""),
            trigger_time_offset=notify_data.get("TriggerTimeOffset", 0.0),
            end_trigger_time_offset=notify_data.get("EndTriggerTimeOffset", 0.0),
            trigger_weight_threshold=notify_data.get("TriggerWeightThreshold", 0.0),
            duration=notify_data.get("Duration", 0.0),
            notify_class=notify_data.get("NotifyClass"),
            notify_state_class=notify_data.get("NotifyStateClass"),
            montage_tick_type=notify_data.get("MontageTickType"),
            notify_trigger_chance=notify_data.get("NotifyTriggerChance", 1.0),
            notify_filter_type=notify_data.get("NotifyFilterType"),
            notify_filter_lod=notify_data.get("NotifyFilterLOD", 0),
            b_converted_from_branching_point=notify_data.get(
                "bConvertedFromBranchingPoint", False
            ),
            track_index=notify_data.get("TrackIndex", 0),
        )
        extract_object_ref(notify_data, "LinkedMontage", notify, "linked_montage")
        extract_object_ref(notify_data, "LinkedSequence", notify, "linked_sequence")
        return notify

    return parse_dict_list(data, _parse_notify)


def parse_float_curve_names(data: Any) -> list[str]:
    """解析浮点曲线名称列表

    从 RawCurveData 属性中提取 FloatCurves 的 Name 字段。
    anim_montage 和 anim_sequence 共享此实现。
    """

    def _parse_curve(curve: dict) -> str | None:
        name_data = curve.get("Name", {})
        if isinstance(name_data, dict):
            curve_name = name_data.get("Name", "")
            if curve_name:
                return curve_name
        return None

    if not isinstance(data, dict):
        return []

    float_curves = data.get("FloatCurves", [])
    return [name for name in parse_dict_list(float_curves, _parse_curve) if name]


def ensure_custom_data(export: Any) -> dict:
    """确保 export 具有 custom_data 属性并返回它

    如果 export 尚未设置 custom_data，则初始化为空字典。
    用于动画和 MovieScene 处理器存储解析结果。
    """
    if not hasattr(export, "custom_data"):
        export.custom_data = {}
    return export.custom_data
