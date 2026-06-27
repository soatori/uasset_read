"""IR（中间表示）数据结构 — PackageIR 层级模型。

IR 是解析结果的统一数据源，渲染器只接收 PackageIR，不访问 ParseResult。
所有 GUID（Node/Pin）统一为 32 位小写 hex。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PackageHeaderIR:
    """包头部精简摘要。"""
    package_name: str
    package_class: str
    package_flags: int
    total_export_count: int
    total_import_count: int
    ue_version: str
    saved_hash: bytes = field(default_factory=lambda: b'')


@dataclass
class PinIR:
    """单个 Pin 的 IR 表示。"""
    pin_name: str
    pin_type: str
    pin_type_value: str | None
    linked_to: list[str]
    direction: str
    default_value: str | None


@dataclass
class NodeIR:
    """单个节点的 IR 表示。"""
    node_guid: str
    node_class: str
    node_comment: str | None
    pins: list[PinIR]
    execution_flow: list[dict]
    macro_expansion: dict | None = None


@dataclass
class GraphIR:
    """单个图的 IR 表示。"""
    graph_guid: str
    graph_name: str
    graph_class: str
    nodes: list[NodeIR]
    execution_chains: list[list[str]]
    subgraphs: list["GraphIR"] = field(default_factory=list)
    graph_type: str | None = None


@dataclass
class PropertyIR:
    """单个属性的 IR 表示。"""
    name: str
    type: str
    value: Any
    array_index: int
    guid: str | None


@dataclass
class ExportRawIR:
    """UE 原始导出表字段（FObjectExport 对应）。

    保留所有 UE 序列化表字段，与解析后的语义字段（ExportIR）隔离。
    """
    class_index: int = 0
    super_index: int = 0
    outer_index: int = 0
    template_index: int = 0
    object_flags: int = 0
    serial_offset: int = 0
    package_flags: int = 0
    b_forced_export: bool = False
    b_not_for_client: bool = False
    b_not_for_server: bool = False
    b_is_inherited_instance: bool = False
    b_not_always_loaded_for_editor_game: bool = True
    b_is_asset: bool = False
    b_generate_public_hash: bool = False
    script_serialization_start_offset: int = 0
    script_serialization_end_offset: int = 0
    guid: str = ""


@dataclass
class ExportIR:
    """单个导出对象的 IR 表示。"""
    index: int
    object_name: str
    object_class: str
    serial_size: int
    outer_index_resolved: str | None
    super_index_resolved: str | None
    parent_class: str | None
    properties: list[PropertyIR]
    graphs: list[GraphIR]
    bulk_data: dict | None
    parse_status: str = "success"
    fallback_reason: str | None = None
    error_message: str | None = None
    asset_type_data: dict | None = None
    ue_export_raw: ExportRawIR | None = None
    diagnostics: dict | None = None


@dataclass
class BlueprintFunctionIR:
    """蓝图函数 IR（完整元数据，等价 UFunction 描述）。"""
    name: str
    return_type: str
    parameters: list[dict]
    function_flags: int = 0
    is_implemented: bool = True  # False = 继承事件占位（如 ReceiveBeginPlay）
    is_pure: bool = False
    is_blueprint_callable: bool = False
    is_const: bool = False
    is_static: bool = False
    is_net: bool = False
    is_net_reliable: bool = False
    is_blueprint_private: bool = False
    access_specifier: str = "Public"
    meta_data: dict = field(default_factory=dict)
    implementation: dict | None = None
    function_graph: dict | None = None
    implementation_status: str = "missing"  # "decompiled"|"graph_only"|"metadata_only"|"missing"


@dataclass
class BlueprintEventIR:
    """蓝图事件 IR（完整元数据，等价蓝图事件描述）。"""
    name: str
    event_type: str
    parameters: list[dict]
    function_flags: int = 0
    is_override: bool = False
    override_parent_class: str = ""
    override_parent_event: str = ""
    is_interface_event: bool = False
    interface_class: str = ""
    is_net: bool = False
    is_net_multicast: bool = False
    is_replicated: bool = False
    is_cosmetic: bool = False
    is_static: bool = False
    meta_data: dict = field(default_factory=dict)
    implementation: dict | None = None
    function_graph: dict | None = None
    implementation_status: str = "missing"  # "decompiled"|"graph_only"|"metadata_only"|"missing"


@dataclass
class BlueprintIR:
    """蓝图元数据 IR（来自 BlueprintMetadata）。"""
    parent_class: str | None
    description: str = ""
    interfaces: list[dict] = field(default_factory=list)
    functions: list[BlueprintFunctionIR] = field(default_factory=list)
    events: list[BlueprintEventIR] = field(default_factory=list)
    components: list[dict] = field(default_factory=list)


@dataclass
class DecompiledFunctionIR:
    """反编译函数 IR（来自 KismetDecompiledResult）。"""
    name: str
    signature: str
    cpp_code: str
    parameters: list[dict]
    return_type: str
    fallback_reasons: list[str] = field(default_factory=list)


@dataclass
class ExecutionChainIR:
    """执行链 IR。"""
    event: str
    chain: list[str]


@dataclass
class LinkerSummaryIR:
    """包链接摘要。"""
    has_linker: bool
    import_paths: list[str]
    export_paths: list[str]


@dataclass
class VariableIR:
    """蓝图变量 IR（完整元数据，等价 FBPVariableDescription）。"""
    name: str
    type: str
    default_value: str | None
    kind: str = "user"  # "user" | "component" | "input_action" | "metadata"
    guid: str | None = None
    category: str = ""
    property_flags: int = 0
    replication_condition: int = 0
    rep_notify_func: str = ""
    friendly_name: str = ""
    metadata: dict = field(default_factory=dict)
    flags_labels: list[str] = field(default_factory=list)
    edit_condition: str = ""
    is_edit_anywhere: bool = False
    is_visible_anywhere: bool = False
    is_blueprint_read_only: bool = False
    is_transient: bool = False
    is_replicated: bool = False
    is_rep_notify: bool = False
    is_expose_on_spawn: bool = False
    is_save_game: bool = False


@dataclass
class PackageIR:
    """顶层 IR 结构。"""
    header: PackageHeaderIR
    name_map: list[str]
    imports: list[dict]
    exports: list[ExportIR]
    linker: LinkerSummaryIR | None
    blueprint: BlueprintIR | None = None
    decompiled_functions: list[DecompiledFunctionIR] = field(default_factory=list)
    execution_chains: list[ExecutionChainIR] = field(default_factory=list)
    variables: list[VariableIR] = field(default_factory=list)
    diagnostics: list = field(default_factory=list)  # List[OffsetRangeDiagnostic]
    function_graphs: list[dict] = field(default_factory=list)  # 顶层函数图数据
    resolved_parent_assets: list[dict] = field(default_factory=list)
    inherited_blueprint_graphs: list[dict] = field(default_factory=list)
    logic_sources: list[dict] = field(default_factory=list)
    soft_object_paths: list[dict] = field(default_factory=list)
    soft_package_references: list[str] = field(default_factory=list)
    depends_map: list[list[int]] = field(default_factory=list)
    resolved_depends_map: list[list[dict]] = field(default_factory=list)
    asset_registry_data_offset: int = 0
    asset_registry_data: dict | None = None
    errors: list[str] = field(default_factory=list)
    status: str = "success"
    status_message: str | None = None
    status_code: str | None = None
    anim_blueprint: AnimBlueprintIR | None = None
    anim_sequence: AnimSequenceIR | None = None
    anim_montage: AnimMontageIR | None = None


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
