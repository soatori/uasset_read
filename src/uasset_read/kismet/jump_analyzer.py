"""Kismet 跳转指令预扫描器。

通过预分析 EX_Jump / EX_JumpIfNot 指令，建立偏移量到表达式索引的映射关系，
并提供 if/else、while、for 等控制流模式的检测能力。

使用方式：
    analyzer = JumpAnalyzer(expressions)
    if_else = analyzer.detect_if_else_pattern(start_idx=0)
    while_loop = analyzer.detect_while_pattern(start_idx=3)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression


class JumpAnalyzer:
    """跳转指令预扫描器，提供偏移量查询和控制流模式检测。

    初始化时预扫描所有表达式，建立以下映射：
    - offset_to_index: 字节偏移量 → 表达式列表索引
    - jump_sources: 跳转目标偏移量 → 跳转源索引列表

    所有检测方法在无法匹配模式时返回 None，不抛出异常。
    """

    def __init__(self, expressions: list[KismetExpression]) -> None:
        self._expressions = expressions
        self._offset_to_index: dict[int, int] = {}
        self._jump_targets: set[int] = set()
        self._jump_sources: dict[int, list[int]] = {}
        self._analyze()

    def _analyze(self) -> None:
        """预扫描所有表达式，建立偏移量映射和跳转源映射。"""
        for idx, expr in enumerate(self._expressions):
            # 表达式自身位置（StatementIndex）→ 索引
            stmt_idx = getattr(expr, "StatementIndex", None)
            if stmt_idx is not None:
                self._offset_to_index[stmt_idx] = idx

            # EX_Jump / EX_JumpIfNot 的目标偏移量
            code_offset = getattr(expr, "CodeOffset", None)
            if code_offset is not None:
                self._jump_targets.add(code_offset)
                self._jump_sources.setdefault(code_offset, []).append(idx)

    def find_label_index(self, offset: int) -> int | None:
        """根据偏移量找到表达式索引。

        Args:
            offset: 目标字节偏移量（通常是 EX_Jump/EX_JumpIfNot 的 CodeOffset）。

        Returns:
            对应的表达式列表索引，未找到时返回 None。
        """
        return self._offset_to_index.get(offset)

    def is_jump_target(self, offset: int) -> bool:
        """判断某个偏移量是否是跳转目标。

        Args:
            offset: 待检查的字节偏移量。

        Returns:
            如果有任何跳转指令指向该偏移量则返回 True。
        """
        return offset in self._jump_targets

    def get_jump_sources(self, target_offset: int) -> list[int]:
        """获取跳转到指定目标的所有源索引。

        Args:
            target_offset: 跳转目标的字节偏移量。

        Returns:
            跳转到该目标的表达式索引列表，无跳转源时返回空列表。
        """
        return list(self._jump_sources.get(target_offset, []))

    def detect_if_else_pattern(self, start_idx: int) -> dict | None:
        """检测 if/else 控制流模式。

        模式特征：
        - start_idx 位置为 EX_JumpIfNot
        - 在 then 分支内查找 EX_Jump（跳到 end_label）
        - 找到 → if/else 模式；未找到 → 简单 if 模式

        Returns:
            {
                "type": "if_else" | "if",
                "start": start_idx,
                "condition": BooleanExpression,
                "then_start": int,
                "then_end": int,       # if/else 模式专属
                "else_start": int,     # if/else 模式专属
                "else_end": int,       # if/else 模式专属
                "end_label": int,      # if/else 模式专属
            }
            无法匹配时返回 None。
        """
        from uasset_read.kismet.expressions.control_flow import EX_JumpIfNot, EX_Jump

        if start_idx < 0 or start_idx >= len(self._expressions):
            return None

        expr = self._expressions[start_idx]
        if not isinstance(expr, EX_JumpIfNot):
            return None

        condition = expr.BooleanExpression
        false_label = expr.CodeOffset

        # 找到 false_label 对应的表达式索引
        false_label_idx = self.find_label_index(false_label)
        if false_label_idx is None:
            return None

        # 在 then 分支中查找 EX_Jump（跳到 end_label）
        # then 分支从 start_idx+1 开始，到 false_label_idx 之前
        for j in range(start_idx + 1, false_label_idx):
            jmp = self._expressions[j]
            if isinstance(jmp, EX_Jump):
                end_label = jmp.CodeOffset
                end_label_idx = self.find_label_index(end_label)
                if end_label_idx is not None and end_label_idx >= false_label_idx:
                    return {
                        "type": "if_else",
                        "start": start_idx,
                        "condition": condition,
                        "then_start": start_idx + 1,
                        "then_end": j,
                        "else_start": false_label_idx,
                        "else_end": end_label_idx,
                        "end_label": end_label,
                    }

        # 未找到 EX_Jump，视为简单 if 模式
        return {
            "type": "if",
            "start": start_idx,
            "condition": condition,
            "then_start": start_idx + 1,
            "then_end": false_label_idx - 1,
        }

    def detect_while_pattern(self, start_idx: int) -> dict | None:
        """检测 while 循环控制流模式。

        模式特征：
        - start_idx 位置为 EX_JumpIfNot，CodeOffset 指向循环出口
        - 循环体内存在 EX_Jump，目标偏移量 <= start_idx 的偏移量（回跳）

        Returns:
            {
                "type": "while",
                "start": start_idx,
                "condition": BooleanExpression,
                "body_start": int,
                "body_end": int,       # 回跳 EX_Jump 的索引
                "exit_label": int,     # 循环出口偏移量
            }
            无法匹配时返回 None。
        """
        from uasset_read.kismet.expressions.control_flow import EX_JumpIfNot, EX_Jump

        if start_idx < 0 or start_idx >= len(self._expressions):
            return None

        expr = self._expressions[start_idx]
        if not isinstance(expr, EX_JumpIfNot):
            return None

        condition = expr.BooleanExpression
        exit_label = expr.CodeOffset

        # 获取 start_idx 表达式的偏移量，用于判断回跳目标
        start_offset = getattr(expr, "StatementIndex", None)
        if start_offset is None:
            return None

        # 在循环体内查找回跳 EX_Jump
        for j in range(start_idx + 1, len(self._expressions)):
            jmp = self._expressions[j]
            if isinstance(jmp, EX_Jump):
                target_offset = jmp.CodeOffset
                # 回跳目标必须在 start_idx 之前或就是 start_idx
                target_idx = self.find_label_index(target_offset)
                if target_idx is not None and target_idx <= start_idx:
                    return {
                        "type": "while",
                        "start": start_idx,
                        "condition": condition,
                        "body_start": start_idx + 1,
                        "body_end": j,
                        "exit_label": exit_label,
                    }

        return None

    def is_while_backjump(self, idx: int) -> bool:
        """判断指定索引是否是某个 while/for 循环的回跳 EX_Jump。

        扫描所有 JumpIfNot 起始的 while 模式，检查 idx 是否是其 body_end。

        Args:
            idx: 待检查的表达式索引。

        Returns:
            如果 idx 是某个 while/for 循环的回跳指令则返回 True。
        """
        from uasset_read.kismet.expressions.control_flow import EX_JumpIfNot

        for start_idx in range(len(self._expressions)):
            if not isinstance(self._expressions[start_idx], EX_JumpIfNot):
                continue
            while_result = self.detect_while_pattern(start_idx)
            if while_result is not None and while_result["body_end"] == idx:
                return True
        return False

    def detect_for_pattern(self, start_idx: int) -> dict | None:
        """检测 for 循环控制流模式。

        模式特征：
        - 类似 while，但循环体末尾包含递增表达式
        - 递增表达式位于回跳 EX_Jump 之前

        Returns:
            {
                "type": "for",
                "start": start_idx,
                "condition": BooleanExpression,
                "body_start": int,
                "body_end": int,       # 回跳 EX_Jump 的索引
                "increment_start": int, # 递增表达式起始索引
                "increment_end": int,   # 递增表达式结束索引（回跳前一个）
                "exit_label": int,     # 循环出口偏移量
            }
            无法匹配时返回 None。
        """
        while_result = self.detect_while_pattern(start_idx)
        if while_result is None:
            return None

        body_end = while_result["body_end"]
        # 递增表达式位于 body_start 到回跳之间
        # 如果 body_start == body_end，说明没有递增，不满足 for 模式
        if body_end <= while_result["body_start"]:
            return None

        return {
            "type": "for",
            "start": while_result["start"],
            "condition": while_result["condition"],
            "body_start": while_result["body_start"],
            "body_end": body_end,
            "increment_start": while_result["body_start"],
            "increment_end": body_end - 1,
            "exit_label": while_result["exit_label"],
        }
