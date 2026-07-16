"""兼容层 — 已废弃的公共导出映射。

通过 `uasset_read.__getattr__` 延迟加载并发出 DeprecationWarning。
新增代码应从子模块直接导入，不要使用这些废弃路径。

仅保留被测试或文档引用的废弃映射，其余已移除。
"""

DEPRECATED_IMPORTS: dict[str, tuple[str, str]] = {
    # --- 测试验证的废弃警告 ---
    "MemoryLimitExceeded": (".memory_safety", "MemoryLimitExceeded"),
    "MemoryPolicy": (".memory_safety", "MemoryPolicy"),
    "ResourceLimits": (".memory_safety", "ResourceLimits"),
    "sanitize_identifier": (".cpp_gen", "sanitize_identifier"),
    # --- wiki 文档引用的废弃路径 ---
    "BlueprintMetadata": (".models", "BlueprintMetadata"),
    "UEdGraph": (".models", "UEdGraph"),
    "PakFileReader": (".pak", "PakFileReader"),
}
