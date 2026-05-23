"""N2C 处理器模块 — 批量注册入口。"""
from uasset_read.n2c.processors.call_function import CallFunctionProcessor
from uasset_read.n2c.processors.cast import CastProcessor
from uasset_read.n2c.processors.event import EventProcessor
from uasset_read.n2c.processors.fallback import FallbackProcessor
from uasset_read.n2c.processors.flow_control import FlowControlProcessor
from uasset_read.n2c.processors.function_entry import FunctionEntryProcessor
from uasset_read.n2c.processors.variable import VariableProcessor

__all__ = [
    "CallFunctionProcessor",
    "CastProcessor",
    "EventProcessor",
    "FallbackProcessor",
    "FlowControlProcessor",
    "FunctionEntryProcessor",
    "VariableProcessor",
    "register_all_processors",
]


def register_all_processors() -> None:
    """批量注册所有处理器到全局注册表（幂等：跳过已注册的类型）。"""
    from uasset_read.n2c.processor_registry import N2CProcessorRegistry

    registry = N2CProcessorRegistry.get_instance()
    for proc_cls in [
        CallFunctionProcessor,
        EventProcessor,
        FunctionEntryProcessor,
        FlowControlProcessor,
        VariableProcessor,
        CastProcessor,
    ]:
        try:
            registry.register(proc_cls())
        except ValueError:
            pass  # Already registered, skip (idempotent)
    if registry._fallback is None:
        registry.set_fallback(FallbackProcessor())
