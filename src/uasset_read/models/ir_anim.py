"""动画蓝图 IR 数据模型 — 从 ir.py 拆分。

包含 AnimNotifyIR、Baked* 系列、AnimBlueprintIR、AnimSequenceIR、AnimMontageIR。
"""
from __future__ import annotations

from dataclasses import dataclass, field


# =============================================================================
# 动画蓝图 IR 数据模型
# =============================================================================


@dataclass
class AnimNotifyIR:
    """FAnimNotifyEvent — 参照 AnimTypes.h:276"""
    notify_name: str                          # FName
    trigger_time_offset: float = 0.0
    end_trigger_time_offset: float = 0.0     # NotifyState 结束偏移
    trigger_weight_threshold: float = 0.0
    duration: float = 0.0                    # NotifyState 时长
    notify_class: str | None = None           # UAnimNotify 类名
    notify_state_class: str | None = None     # UAnimNotifyState 类名
    montage_tick_type: str | None = None      # MontageNotifyTickType
    notify_trigger_chance: float = 1.0
    notify_filter_type: str | None = None
    notify_filter_lod: int = 0
    b_converted_from_branching_point: bool = False
    track_index: int = 0
    linked_montage: str | None = None         # FPackageIndex 路径
    linked_sequence: str | None = None        # FPackageIndex 路径


@dataclass
class BakedExitTransitionIR:
    """FBakedStateExitTransition — 参照 AnimStateMachineTypes.h:254"""
    can_take_delegate_index: int = -1
    custom_result_node_index: int = -1
    transition_index: int = -1                # → FAnimationTransitionBetweenStates
    b_desired_transition_return_value: bool = True
    b_automatic_remaining_time_rule: bool = False
    automatic_rule_trigger_time: float = 0.0
    b_only_evaluate_when_active: bool = False


@dataclass
class BakedStateIR:
    """FBakedAnimationState — 参照 AnimStateMachineTypes.h:312"""
    state_name: str                           # FName
    state_root_node_index: int = -1
    player_node_indices: list[int] = field(default_factory=list)
    layer_node_indices: list[int] = field(default_factory=list)
    entry_rule_node_index: int = -1
    start_notify: int = -1                    # AnimNotifies 数组索引
    end_notify: int = -1
    fully_blended_notify: int = -1
    b_always_reset_on_entry: bool = False
    b_is_a_conduit: bool = False
    transitions: list[BakedExitTransitionIR] = field(default_factory=list)


@dataclass
class BakedTransitionIR:
    """FAnimationTransitionBetweenStates — 参照 AnimStateMachineTypes.h:186"""
    previous_state: int = -1
    next_state: int = -1
    crossfade_duration: float = 0.0
    min_time_before_reentry: float = 0.0
    blend_mode: str | None = None            # EAlphaBlendOption
    logic_type: str | None = None            # ETransitionLogicType
    start_notify: int = -1
    end_notify: int = -1
    interrupt_notify: int = -1
    custom_curve: str | None = None           # FPackageIndex 路径
    blend_profile: str | None = None          # FPackageIndex 路径


@dataclass
class BakedStateMachineIR:
    """FBakedAnimationStateMachine — 参照 AnimStateMachineTypes.h:368"""
    machine_name: str                        # FName
    initial_state: int = 0
    states: list[BakedStateIR] = field(default_factory=list)
    transitions: list[BakedTransitionIR] = field(default_factory=list)


@dataclass
class AnimBlueprintIR:
    """UAnimBlueprintGeneratedClass 动画特有数据"""
    target_skeleton: str | None = None        # FPackageIndex 路径
    baked_state_machines: list[BakedStateMachineIR] = field(default_factory=list)
    anim_notifies: list[AnimNotifyIR] = field(default_factory=list)
    sync_group_names: list[str] = field(default_factory=list)
    graph_asset_player_info: dict = field(default_factory=dict)
    graph_blend_options: dict = field(default_factory=dict)
    anim_node_data: list[dict] = field(default_factory=list)  # FAnimNodeData 原始


@dataclass
class AnimSequenceIR:
    """UAnimSequence 元数据（不含压缩轨迹数据）"""
    target_skeleton: str | None = None        # FPackageIndex 路径
    additive_anim_type: str | None = None     # EAdditiveAnimationType
    ref_pose_type: str | None = None          # EAnimPoseType
    ref_frame_index: int = 0
    ref_pose_seq: str | None = None           # FPackageIndex 路径
    retarget_source: str | None = None
    interpolation: str | None = None          # EAnimInterpolationType
    b_enable_root_motion: bool = False
    root_motion_root_lock: str | None = None  # ERootMotionRootLock
    rate_scale: float = 1.0
    sequence_length: float = 0.0
    notifies: list[AnimNotifyIR] = field(default_factory=list)
    float_curve_names: list[str] = field(default_factory=list)
    bone_compression_settings: str | None = None  # FPackageIndex 路径
    curve_compression_settings: str | None = None  # FPackageIndex 路径
    has_compressed_data: bool = False

    # 轨迹数据（FCompressedAnimSequence）
    compressed_track_count: int = 0          # CompressedTrackToSkeletonMapTable 长度
    compressed_byte_stream_size: int = 0     # CompressedByteStream 字节数
    compressed_raw_data_size: int = 0        # 压缩前原始数据大小
    bone_compression_codec: str | None = None  # 骨骼压缩编解码器名称
    curve_compression_codec: str | None = None  # 曲线压缩编解码器名称


@dataclass
class AnimMontageIR:
    """UAnimMontage 元数据"""
    blend_mode_in: str | None = None          # EAlphaBlendOption
    blend_mode_out: str | None = None         # EAlphaBlendOption
    blend_in_alpha: float = 0.0
    blend_in_option: str | None = None
    blend_out_alpha: float = 0.0
    blend_out_option: str | None = None
    blend_out_trigger_time: float = 0.0
    sync_group: str | None = None
    sync_slot_index: int = 0
    b_enable_auto_blend_out: bool = True
    composite_sections: list[dict] = field(default_factory=list)
    slot_anim_tracks: list[dict] = field(default_factory=list)
    branching_point_markers: list[dict] = field(default_factory=list)
    notifies: list[AnimNotifyIR] = field(default_factory=list)
    float_curve_names: list[str] = field(default_factory=list)
    rate_scale: float = 1.0
