"""Animation Blueprint IR data models — split from ir.py.

Contains AnimNotifyIR, Baked* series, AnimBlueprintIR, AnimSequenceIR, AnimMontageIR.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# =============================================================================
# Animation Blueprint IR Data Models
# =============================================================================


@dataclass
class AnimNotifyIR:
    """FAnimNotifyEvent — reference: AnimTypes.h:276"""

    notify_name: str  # FName
    trigger_time_offset: float = 0.0
    end_trigger_time_offset: float = 0.0  # NotifyState end offset
    trigger_weight_threshold: float = 0.0
    duration: float = 0.0  # NotifyState duration
    notify_class: str | None = None  # UAnimNotify class name
    notify_state_class: str | None = None  # UAnimNotifyState class name
    montage_tick_type: str | None = None  # MontageNotifyTickType
    notify_trigger_chance: float = 1.0
    notify_filter_type: str | None = None
    notify_filter_lod: int = 0
    b_converted_from_branching_point: bool = False
    track_index: int = 0
    linked_montage: str | None = None  # FPackageIndex path
    linked_sequence: str | None = None  # FPackageIndex path


@dataclass
class BakedExitTransitionIR:
    """FBakedStateExitTransition — reference: AnimStateMachineTypes.h:254"""

    can_take_delegate_index: int = -1
    custom_result_node_index: int = -1
    transition_index: int = -1  # → FAnimationTransitionBetweenStates
    b_desired_transition_return_value: bool = True
    b_automatic_remaining_time_rule: bool = False
    automatic_rule_trigger_time: float = 0.0
    b_only_evaluate_when_active: bool = False


@dataclass
class BakedStateIR:
    """FBakedAnimationState — reference: AnimStateMachineTypes.h:312"""

    state_name: str  # FName
    state_root_node_index: int = -1
    player_node_indices: list[int] = field(default_factory=list)
    layer_node_indices: list[int] = field(default_factory=list)
    entry_rule_node_index: int = -1
    start_notify: int = -1  # AnimNotifies array index
    end_notify: int = -1
    fully_blended_notify: int = -1
    b_always_reset_on_entry: bool = False
    b_is_a_conduit: bool = False
    transitions: list[BakedExitTransitionIR] = field(default_factory=list)


@dataclass
class BakedTransitionIR:
    """FAnimationTransitionBetweenStates — reference: AnimStateMachineTypes.h:186"""

    previous_state: int = -1
    next_state: int = -1
    crossfade_duration: float = 0.0
    min_time_before_reentry: float = 0.0
    blend_mode: str | None = None  # EAlphaBlendOption
    logic_type: str | None = None  # ETransitionLogicType
    start_notify: int = -1
    end_notify: int = -1
    interrupt_notify: int = -1
    custom_curve: str | None = None  # FPackageIndex path
    blend_profile: str | None = None  # FPackageIndex path


@dataclass
class BakedStateMachineIR:
    """FBakedAnimationStateMachine — reference: AnimStateMachineTypes.h:368"""

    machine_name: str  # FName
    initial_state: int = 0
    states: list[BakedStateIR] = field(default_factory=list)
    transitions: list[BakedTransitionIR] = field(default_factory=list)


@dataclass
class AnimBlueprintIR:
    """UAnimBlueprintGeneratedClass animation-specific data."""

    target_skeleton: str | None = None  # FPackageIndex path
    baked_state_machines: list[BakedStateMachineIR] = field(default_factory=list)
    anim_notifies: list[AnimNotifyIR] = field(default_factory=list)
    sync_group_names: list[str] = field(default_factory=list)
    graph_asset_player_info: dict = field(default_factory=dict)
    graph_blend_options: dict = field(default_factory=dict)
    anim_node_data: list[dict] = field(default_factory=list)  # FAnimNodeData raw


@dataclass
class AnimSequenceIR:
    """UAnimSequence metadata (excludes compressed track data)."""

    target_skeleton: str | None = None  # FPackageIndex path
    additive_anim_type: str | None = None  # EAdditiveAnimationType
    ref_pose_type: str | None = None  # EAnimPoseType
    ref_frame_index: int = 0
    ref_pose_seq: str | None = None  # FPackageIndex path
    retarget_source: str | None = None
    interpolation: str | None = None  # EAnimInterpolationType
    b_enable_root_motion: bool = False
    root_motion_root_lock: str | None = None  # ERootMotionRootLock
    rate_scale: float = 1.0
    sequence_length: float = 0.0
    notifies: list[AnimNotifyIR] = field(default_factory=list)
    float_curve_names: list[str] = field(default_factory=list)
    bone_compression_settings: str | None = None  # FPackageIndex path
    curve_compression_settings: str | None = None  # FPackageIndex path
    has_compressed_data: bool = False

    # Track data (FCompressedAnimSequence)
    compressed_track_count: int = 0  # CompressedTrackToSkeletonMapTable length
    compressed_byte_stream_size: int = 0  # CompressedByteStream byte count
    compressed_raw_data_size: int = 0  # Pre-compression raw data size
    bone_compression_codec: str | None = None  # Bone compression codec name
    curve_compression_codec: str | None = None  # Curve compression codec name


@dataclass
class AnimMontageIR:
    """UAnimMontage metadata."""

    blend_mode_in: str | None = None  # EAlphaBlendOption
    blend_mode_out: str | None = None  # EAlphaBlendOption
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
