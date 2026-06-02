"""N2C 节点处理器注册表 — 函数式懒初始化。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Optional

from uasset_read.n2c.node_types import N2CNodeType

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition
    from uasset_read.n2c.processor_base import N2CNodeProcessor

logger = logging.getLogger(__name__)


class N2CProcessorRegistry:
    """节点处理器注册表。

    负责注册、查找和调度 N2CNodeProcessor 实例。
    支持设置 fallback 处理器处理未知类型。
    """

    def __init__(self) -> None:
        self._processors: Dict[N2CNodeType, N2CNodeProcessor] = {}
        self._fallback: Optional[N2CNodeProcessor] = None

    def register(self, processor: N2CNodeProcessor) -> None:
        """注册处理器。

        Args:
            processor: N2CNodeProcessor 实例

        Raises:
            ValueError: 如果节点类型已被注册
        """
        for node_type in processor.node_types:
            if node_type in self._processors:
                existing = self._processors[node_type]
                raise ValueError(
                    f"Node type {node_type.value!r} already registered "
                    f"by {type(existing).__name__}, cannot register {type(processor).__name__}"
                )
            self._processors[node_type] = processor
            logger.debug("Registered processor %s for type %s", type(processor).__name__, node_type.value)

    def set_fallback(self, processor: N2CNodeProcessor) -> None:
        """设置默认回退处理器。

        当没有处理器匹配节点类型时使用。
        """
        self._fallback = processor
        logger.debug("Set fallback processor: %s", type(processor).__name__)

    def get_processor(self, node_type: N2CNodeType) -> Optional[N2CNodeProcessor]:
        """获取指定类型的处理器。

        如果没有精确匹配但有 fallback，返回 fallback。
        如果都没有，返回 None。
        """
        if node_type in self._processors:
            return self._processors[node_type]
        return self._fallback

    def process_node(
        self,
        node: UEdGraphNode,
        node_type: N2CNodeType,
        definition: N2CNodeDefinition,
    ) -> bool:
        """统一处理入口。

        Args:
            node: 原始 UEdGraphNode
            node_type: 语义类型
            definition: 要填充的 N2CNodeDefinition

        Returns:
            True 如果处理成功，False 如果没有处理器或处理失败
        """
        processor = self.get_processor(node_type)
        if processor is None:
            logger.warning("No processor registered for node type %s", node_type.value)
            return False

        try:
            processor.process(node, definition)
            return True
        except Exception as exc:
            logger.warning(
                "Processor %s failed for node type %s: %s",
                type(processor).__name__,
                node_type.value,
                exc,
            )
            return False


_default_registry: Optional[N2CProcessorRegistry] = None


def get_registry() -> N2CProcessorRegistry:
    """获取默认处理器注册表（懒初始化）。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = N2CProcessorRegistry()
        _register_default_processors(_default_registry)
    return _default_registry


def reset_registry() -> None:
    """重置默认注册表，用于测试隔离。"""
    global _default_registry
    _default_registry = None


def _register_default_processors(registry: N2CProcessorRegistry) -> None:
    """注册所有默认处理器到给定注册表（幂等：跳过已注册的类型）。"""
    from uasset_read.n2c.processors import (
        # 原有处理器
        CallFunctionProcessor,
        CommentProcessor,
        DelegateProcessor,
        EnhancedInputActionProcessor,
        EventProcessor,
        FlowControlProcessor,
        FunctionEntryProcessor,
        VariableProcessor,
        CastProcessor,
        WidgetProcessor,
        FallbackProcessor,
        # flow_control 扩展
        MultiGateProcessor,
        DoOnceProcessor,
        SelectProcessor,
        EaseFunctionProcessor,
        ForEachEnumProcessor,
        MapForEachProcessor,
        SetForEachProcessor,
        # struct_ops
        StructOpsProcessor,
        MakeArrayProcessor,
        MakeMapProcessor,
        MakeSetProcessor,
        # variable_ops
        LocalVariableProcessor,
        CreateDelegateProcessor,
        ClearDelegateProcessor,
        RemoveDelegateProcessor,
        DelegateSetProcessor,
        StructMemberGetProcessor,
        StructMemberSetProcessor,
        SetFieldsInStructProcessor,
        # utilities
        AsyncActionProcessor,
        TimelineProcessor,
        FormatTextProcessor,
        MathExpressionProcessor,
        GetEnumeratorNameProcessor,
        GetEnumeratorNameAsStringProcessor,
        GetNumEnumEntriesProcessor,
        EnumComparisonProcessor,
    )
    for proc_cls in [
        # 原有处理器
        CallFunctionProcessor,
        CommentProcessor,
        DelegateProcessor,
        EnhancedInputActionProcessor,
        EventProcessor,
        FunctionEntryProcessor,
        FlowControlProcessor,
        VariableProcessor,
        CastProcessor,
        WidgetProcessor,
        # flow_control 扩展
        MultiGateProcessor,
        DoOnceProcessor,
        SelectProcessor,
        EaseFunctionProcessor,
        ForEachEnumProcessor,
        MapForEachProcessor,
        SetForEachProcessor,
        # struct_ops
        StructOpsProcessor,
        MakeArrayProcessor,
        MakeMapProcessor,
        MakeSetProcessor,
        # variable_ops
        LocalVariableProcessor,
        CreateDelegateProcessor,
        ClearDelegateProcessor,
        RemoveDelegateProcessor,
        DelegateSetProcessor,
        StructMemberGetProcessor,
        StructMemberSetProcessor,
        SetFieldsInStructProcessor,
        # utilities
        AsyncActionProcessor,
        TimelineProcessor,
        FormatTextProcessor,
        MathExpressionProcessor,
        GetEnumeratorNameProcessor,
        GetEnumeratorNameAsStringProcessor,
        GetNumEnumEntriesProcessor,
        EnumComparisonProcessor,
    ]:
        try:
            registry.register(proc_cls())
        except ValueError:
            pass  # Already registered, skip (idempotent)
    if registry._fallback is None:
        registry.set_fallback(FallbackProcessor())
