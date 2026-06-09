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
    functions: list[BlueprintFunctionIR]
    events: list[BlueprintEventIR]
    components: list[dict]


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
    errors: list[str] = field(default_factory=list)
    status: str = "success"
    status_message: str | None = None
    status_code: str | None = None
