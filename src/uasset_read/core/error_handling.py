"""统一错误处理模式 — 容错解析上下文管理器。

将重复的 try/except ParseError + result.errors.append 模式
收敛为声明式上下文管理器，减少样板代码并统一错误消息格式。
"""

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


@contextmanager
def tolerant_parse(
    result: "ParseResult | LinkerParseResult",
    stage: str,
):
    """容错解析上下文管理器。

    用法::

        with tolerant_parse(result, "blueprint extraction"):
            do_something()

    行为:
        捕获 ParseError → 记录到 result.errors → 重新抛出

    Args:
        result: ParseResult 或 LinkerParseResult 对象（必须有 errors 属性）
        stage: 阶段名称，用于错误消息前缀
    """
    try:
        yield
    except ParseError as e:
        error_msg = f"{stage} error: {e}"
        if error_msg not in result.errors:
            result.errors.append(error_msg)
        raise
