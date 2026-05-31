"""
蓝图元数据数据类 — BlueprintMetadata, BlueprintVariable, BlueprintFunction,
BlueprintEvent, FunctionParameter, MulticastDelegate。

等价覆盖 uasset_read.py 中第 1655-1870 行的数据类定义。
Per D-06: 数据和序列化解耦，from_archive 为 stub。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.models.core import FEdGraphPinType


def _raise_metadata_from_archive_not_supported() -> None:
    raise NotImplementedError(
        "Blueprint metadata models are populated by "
        "extract_blueprint_metadata(); direct from_archive() parsing is not "
        "implemented for these DTO classes"
    )


@dataclass
class FunctionParameter:
    """函数参数（META-02）。"""
    name: str = ""
    param_type: str = ""
    default_value: Any = None
    is_input: bool = True
    is_output: bool = False
    is_optional: bool = False
    property_flags: int = 0
    meta_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_archive(cls, archive: FArchive) -> "FunctionParameter":
        _raise_metadata_from_archive_not_supported()


@dataclass
class MulticastDelegate:
    """多播委托。"""
    delegate_name: str = ""
    signature_function: str = ""
    is_callable_in_blueprint: bool = False

    @classmethod
    def from_archive(cls, archive: FArchive) -> "MulticastDelegate":
        _raise_metadata_from_archive_not_supported()


@dataclass
class BlueprintEvent:
    """蓝图事件元数据。"""
    name: str = ""
    event_type: str = ""
    function_flags: int = 0
    is_blueprint_event: bool = False
    is_blueprint_implementable_event: bool = False
    is_net: bool = False
    is_net_multicast: bool = False
    is_net_reliable: bool = False
    is_net_client: bool = False
    is_net_server: bool = False
    is_replicated: bool = False
    is_cosmetic: bool = False
    is_static: bool = False
    is_multicast: bool = False
    multicast_delegate: Optional[MulticastDelegate] = None
    is_override: bool = False
    override_parent_class: str = ""
    override_parent_event: str = ""
    is_interface_event: bool = False
    interface_class: str = ""
    parameters: List[FunctionParameter] = field(default_factory=list)
    meta_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_archive(cls, archive: FArchive) -> "BlueprintEvent":
        _raise_metadata_from_archive_not_supported()


@dataclass
class BlueprintFunction:
    """蓝图函数元数据。"""
    name: str = ""
    return_type: str = ""
    parameters: List[FunctionParameter] = field(default_factory=list)
    function_flags: int = 0
    is_pure: bool = False
    is_blueprint_callable: bool = False
    is_blueprint_event: bool = False
    is_blueprint_implementable_event: bool = False
    is_native: bool = False
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_exec: bool = False
    is_net: bool = False
    is_net_reliable: bool = False
    is_net_server: bool = False
    is_net_client: bool = False
    is_net_multicast: bool = False
    is_blueprint_private: bool = False
    is_blueprint_protected: bool = False
    is_blueprint_public: bool = False
    is_blueprint_pure: bool = False
    is_blueprint_cosmetic: bool = False
    is_editor_only: bool = False
    is_final: bool = False
    is_delegate: bool = False
    is_multicast_delegate: bool = False
    is_has_out_parms: bool = False
    is_has_defaults: bool = False
    access_specifier: str = "Public"
    meta_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_archive(cls, archive: FArchive) -> "BlueprintFunction":
        _raise_metadata_from_archive_not_supported()


@dataclass
class BlueprintVariable:
    """蓝图变量定义（FBPVariableDescription）。"""
    var_name: str
    var_type: Optional["FEdGraphPinType"] = None
    category: str = ""
    property_flags: int = 0
    var_guid: str = ""
    rep_notify_func: str = ""
    replication_condition: int = 0
    default_value: Any = None
    friendly_name: str = ""
    is_component: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    flags_labels: List[str] = field(default_factory=list)
    edit_condition: str = ""
    meta_class: str = ""
    is_edit_anywhere: bool = False
    is_edit_instance_only: bool = False
    is_visible_anywhere: bool = False
    is_blueprint_read_only: bool = False
    is_blueprint_readable: bool = False
    is_blueprint_writable: bool = False
    is_transient: bool = False
    is_duplicate_transient: bool = False
    is_text_export_transient: bool = False
    is_non_transient: bool = False
    is_export_object: bool = False
    is_save_game: bool = False
    is_no_clear: bool = False
    is_reference_only: bool = False
    is_blueprint_assignable: bool = False
    is_blueprint_callable: bool = False
    is_net: bool = False
    is_replicated: bool = False
    is_rep_notify: bool = False
    is_interp: bool = False
    is_non_pi_ed_duplicate_transient: bool = False
    is_expose_on_spawn: bool = False
    edit_category: str = ""
    edit_widget: str = ""

    @classmethod
    def from_archive(cls, archive: FArchive) -> "BlueprintVariable":
        _raise_metadata_from_archive_not_supported()


@dataclass
class BlueprintMetadata:
    """Blueprint 元数据，从 ExportMap 提取。"""
    is_blueprint: bool
    parent_class: Optional[str] = None
    variables: List[BlueprintVariable] = field(default_factory=list)
    detection_warning: Optional[str] = None
    functions: List[BlueprintFunction] = field(default_factory=list)
    events: List[BlueprintEvent] = field(default_factory=list)

    @classmethod
    def from_archive(cls, archive: FArchive) -> "BlueprintMetadata":
        _raise_metadata_from_archive_not_supported()
