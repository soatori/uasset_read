from __future__ import annotations

"""IR（中间表示）数据结构 — PackageIR 层级模型。

IR 是解析结果的统一数据源，渲染器只接收 PackageIR，不访问 ParseResult。
所有 GUID（Node/Pin）统一为 32 位小写 hex。

分层说明：
- 本模块（ir.py）定义呈现模型，面向渲染器的简化表示（str 类型、str 方向等）
- models/core.py 定义序列化模型，保留 UE 原始类型（int 方向、嵌套对象等）
- IR Builder 负责从序列化模型（UEdGraph*）转换为呈现模型（GraphIR*）
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PackageHeaderIR:
    """包头信息，与 UE 文件格式完全对齐。

    字段来源于 PackageFileSummary（UE 的 FPackageFileSummary）。
    """
    # 核心字段（必填）
    package_name: str
    package_class: str
    package_flags: int
    total_export_count: int
    total_import_count: int
    ue_version: str
    saved_hash: bytes = field(default_factory=lambda: b'')

    # 文件版本
    file_version_ue4: int = 0
    file_version_ue5: int = 0
    file_version_licensee: int = 0

    # 头部结构偏移
    total_header_size: int = 0
    custom_versions: list[dict] = field(default_factory=list)
    folder_name: str = ""

    # 名称表
    name_count: int = 0
    name_offset: int = 0

    # 软引用路径表
    soft_object_paths_count: int = 0
    soft_object_paths_offset: int = 0

    # 本地化
    localization_id: str = ""

    # 可收集文本数据
    gatherable_text_data_count: int = 0
    gatherable_text_data_offset: int = 0

    # 导出/导入表
    export_count: int = 0
    export_offset: int = 0
    import_count: int = 0
    import_offset: int = 0

    # 元数据
    metadata_offset: int = 0

    # 依赖表
    depends_offset: int = 0

    # 软包引用
    soft_package_references_count: int = 0
    soft_package_references_offset: int = 0

    # 可搜索名称
    searchable_names_offset: int = 0

    # 缩略图表
    thumbnail_table_offset: int = 0

    # 导入类型层级
    import_type_hierarchies_count: int = 0
    import_type_hierarchies_offset: int = 0

    # 持久化 GUID
    persistent_guid: str = "00000000000000000000000000000000"

    # 版本世代
    generations: list[dict] = field(default_factory=list)

    # 引擎版本
    saved_by_engine_version: str = ""
    compatible_with_engine_version: str = ""

    # 压缩
    compression_flags: int = 0

    # 包来源
    package_source: int = 0

    # 批量数据
    bulk_data_start_offset: int = 0

    # 世界分块信息
    world_tile_info_data_offset: int = 0

    # 分块 ID
    chunk_ids: list[int] = field(default_factory=list)

    # 预加载依赖
    preload_dependency_count: int = 0
    preload_dependency_offset: int = 0

    # 名称引用计数
    names_referenced_from_export_data_count: int = 0

    # Payload TOC
    payload_toc_offset: int = 0

    # 数据资源
    data_resource_offset: int = 0


@dataclass
class PinIR:
    """单个 Pin 的呈现模型（IR 层）。

    与序列化模型 UEdGraphPin 的区别：
    - direction 为 str（"EGPD_Input"/"EGPD_Output"），而非 int
    - pin_category/pin_subcategory 等结构化字段替代 _safe_str() 的 FEdGraphPinType 字符串化
    - linked_to 为 str GUID 列表，而非 UObjectInstance 列表

    新增字段（v0.5.2）对应 FEdGraphPinType 的 10 个结构化属性：
    - pin_category: Pin 类型大类（"bool"/"int"/"float"/"object"/"struct"/"exec" 等）
    - pin_subcategory: Pin 类型子类（如 "bool"→"int" 的子类型路径）
    - pin_subcategory_object: PinSubCategoryObject 解析后的对象名（如 "/Script/Engine.Actor"）
    - container_type: 容器类型（"None"/"Array"/"Set"/"Map"），对应 EPinContainerType
    - is_reference: 是否按引用传递
    - is_const: 是否不可变常量
    - is_weak_pointer: 是否弱引用
    - is_uobject_wrapper: 是否 UObject 包装类型（如 TSubclassOf）
    - is_map_key: Map 容器的 key 类型标记（来自 PinValueType）
    - is_map_value: Map 容器的 value 类型标记（来自 PinValueType）
    """
    pin_name: str
    pin_type: str  # 保留向后兼容：FEdGraphPinType 的 _safe_str() 输出
    linked_to: list[str]
    direction: str
    default_value: str | None
    pin_guid: str = ""  # Pin GUID（用于建立 pin_guid -> node_guid 索引）
    # --- 结构化类型字段（FEdGraphPinType 拆解） ---
    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: str | None = None
    container_type: str = "None"
    is_reference: bool = False
    is_const: bool = False
    is_weak_pointer: bool = False
    is_uobject_wrapper: bool = False
    is_map_key: bool = False
    is_map_value: bool = False
    # Map terminal 类型字段（Map 容器专用）
    map_key_pin_category: str = ""
    map_key_pin_subcategory: str = ""
    map_key_pin_subcategory_object: str | None = None


@dataclass
class NodeIR:
    """单个节点的呈现模型（IR 层）。

    与序列化模型 UEdGraphNode 的区别：
    - node_class 为 str，对应 UEdGraphNode.class_name
    - pins 为 list[PinIR]，而非 list[UEdGraphPin]
    - 包含 execution_flow 和 macro_expansion 等 IR 特有字段
    - 不包含 node_pos_x/y（渲染器不需要）
    """
    node_guid: str
    node_class: str
    node_comment: str | None
    pins: list[PinIR]
    execution_flow: list[dict]
    macro_expansion: dict | None = None
    # Enhanced Input 相关字段（v0.5.2）
    input_action_path: str | None = None  # Input Action 资产路径
    trigger_events: list[dict] = field(default_factory=list)  # 触发事件列表
    event_type: str | None = None  # 事件类型（Triggered/Completed/Started/Stopped/Ongoing）


@dataclass
class GraphIR:
    """单个图的呈现模型（IR 层）。

    与序列化模型 UEdGraph 的区别：
    - nodes 为 list[NodeIR]，而非 list[UEdGraphNode]
    - 包含 execution_chains 等 IR 特有字段
    - 不包含 schema/b_editable（渲染器不需要）
    """
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
    b_not_always_loaded_for_editor_game: bool = False
    b_is_asset: bool = False
    b_generate_public_hash: bool = False
    script_serialization_start_offset: int = 0
    script_serialization_end_offset: int = 0
    guid: str = ""


@dataclass
class ImportIR:
    """单个导入对象的 IR 表示，与 UE 的 FObjectImport 对齐。"""
    index: int
    class_package: str
    class_name: str
    object_name: str
    outer_index: int = 0
    is_asset: bool = False
    package_flags: int = 0
    outer_index_resolved: str | None = None
    package_name: str = ""
    b_import_optional: bool = False


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
    anim_blueprint: AnimBlueprintIR | None = None
    anim_sequence: AnimSequenceIR | None = None
    anim_montage: AnimMontageIR | None = None
    ue_export_raw: ExportRawIR | None = None
    diagnostics: dict | None = None
    # 懒加载标记
    is_loaded: bool = False
    lazy_load_archive: bytes | None = None
    # 直接访问字段（从 ExportRawIR 提升，方便渲染层直接读取）
    template_index: int = 0
    object_flags: int = 0
    package_flags: int = 0
    b_forced_export: bool = False
    b_not_for_client: bool = False
    b_not_for_server: bool = False
    b_is_asset: bool = False
    b_generate_public_hash: bool = False
    b_not_always_loaded_for_editor_game: bool = False
    guid: str = ""


@dataclass
class ExportDependencyIR:
    """Export 依赖关系。

    对应 UE 的 FExportMapEntry 中的依赖关系字段。
    用于描述 export 之间的序列化和创建顺序依赖。
    """
    export_index: int
    serialization_before_serialization: list[int]
    create_before_serialization: list[int]
    serialization_before_create: list[int]
    create_before_create: list[int]


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
    bytecode_confidence: str = "verified"  # "verified" | "fallback" | "heuristic"


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
class SourceSiteContextIR:
    """本地化上下文信息 — FTextSourceSiteContext。

    参照 GatherableTextData.h:12
    描述文本在源代码中的使用位置及其本地化属性。
    """
    key_name: str
    site_description: str
    is_editor_only: bool
    is_optional: bool


@dataclass
class GatherableTextDataIR:
    """可收集文本数据 — FGatherableTextData。

    参照 GatherableTextData.h:49
    包含命名空间名称、源字符串和来源上下文列表。
    """
    namespace_name: str
    source_string: str
    source_site_contexts: list[SourceSiteContextIR]


@dataclass
class HexViewEntryIR:
    """单次读取操作的 IR 表示（从 HexViewEntry 转换而来）。"""
    key: str
    type: str
    value: Any
    start: int
    stop: int
    size: int
    field_path: str | None = None
    semantic_type: str | None = None
    value_hex: str | None = None
    value_size: int | None = None


@dataclass
class DebugIR:
    """调试数据 IR（解析轨迹信息）。"""
    hex_view: list[HexViewEntryIR] = field(default_factory=list)


@dataclass
class PackageIR:
    """顶层 IR 结构。"""
    header: PackageHeaderIR
    name_map: tuple[str, ...]
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
    debug: DebugIR | None = None


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
