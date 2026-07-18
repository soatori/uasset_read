"""Opaque handler 工厂函数 — 消除重复的 partial metadata handler 代码。

所有返回 partial_metadata 的 opaque handler 共享相同逻辑：
读取当前位置最多 256 字节样本，返回 raw_offset + sample_size + parse_status。
使用 make_opaque_stub() 生成，避免每个类型一个空壳文件。
"""

from typing import Any, Callable
from ...models.validators import validate_parse_status


def make_opaque_stub(class_name: str) -> Callable[[Any, list[str]], dict[str, Any]]:
    """创建一个 opaque partial metadata handler。

    生成的函数读取当前 archive 位置最多 256 字节样本，
    返回包含 raw_offset、sample_size、parse_status 的字典。

    Args:
        class_name: UE class 名称（用于日志/诊断）

    Returns:
        解析函数，签名为 (archive, name_map) -> dict
    """

    def _parse(archive: Any, name_map: list[str]) -> dict[str, Any]:
        start = archive.tell()
        remaining = max(0, archive.total_size() - start)
        sample = archive.read(min(remaining, 256))
        return {
            "raw_offset": start,
            "sample_size": len(sample),
            "parse_status": validate_parse_status("partial_metadata"),
        }

    return _parse
