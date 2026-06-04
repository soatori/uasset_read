"""Kismet 跳转指令预扫描器。

通过预分析 EX_Jump / EX_JumpIfNot / EX_SwitchValue 指令，建立偏移量到表达式索引的映射关系，
并提供 if/else、while、for、switch/case 等控制流模式的检测能力。

使用方式：
    analyzer = JumpAnalyzer(expressions)
    pattern = analyzer.detect_pattern(start_idx=0)
    stats = analyzer.analyze_structured_rate()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression


# 赋值类表达式类型，用于识别 for 循环的递增语句
_ASSIGNMENT_TYPES: tuple[type, ...] = ()
_ASSIGNMENT_TOKENS: frozenset[int] = frozenset()


def _get_assignment_types() -> tuple[type, ...]:
    """延迟加载赋值类型元组，避免循环导入。"""
    global _ASSIGNMENT_TYPES
    if not _ASSIGNMENT_TYPES:
        from uasset_read.kismet.expressions.assignments import (
            EX_Let, EX_LetBool, EX_LetObj, EX_LetWeakObjPtr,
            EX_LetValueOnPersistentFrame,
        )
        _ASSIGNMENT_TYPES = (
            EX_Let, EX_LetBool, EX_LetObj, EX_LetWeakObjPtr,
            EX_LetValueOnPersistentFrame,
        )
    return _ASSIGNMENT_TYPES


def _is_assignment(expr: object) -> bool:
    """判断表达式是否是赋值类型。"""
    return isinstance(expr, _get_assignment_types())


@dataclass
class StructuredRateReport:
    """结构化率分析报告。

    Attributes:
        total_jump_exprs: 总跳转指令数（EX_Jump + EX_JumpIfNot + EX_ComputedJump）
        structured_count: 被结构化匹配的跳转指令数
        goto_count: 回退到 goto 的跳转指令数
        rate: 结构化率（0.0 ~ 1.0）
        pattern_counts: 各模式命中次数 {"if_else": N, "if": N, "while": N, "for": N, "switch": N}
        goto_reasons: goto 回退原因列表 [{"index": int, "reason": str, "expr_type": str}]
    """

    total_jump_exprs: int = 0
    structured_count: int = 0
    goto_count: int = 0
    rate: float = 0.0
    pattern_counts: dict[str, int] = field(default_factory=dict)
    goto_reasons: list[dict] = field(default_factory=list)


class JumpAnalyzer:
    """跳转指令预扫描器，提供偏移量查询和控制流模式检测。

    初始化时预扫描所有表达式，建立以下映射：
    - offset_to_index: 字节偏移量 → 表达式列表索引
    - jump_sources: 跳转目标偏移量 → 跳转源索引列表

    支持的控制流模式：
    - if / if_else: EX_JumpIfNot 条件分支
    - while: EX_JumpIfNot + 回跳 EX_Jump
    - for: while + 赋值递增表达式
    - switch/case: EX_SwitchValue 多分支选择

    所有检测方法在无法匹配模式时返回 None，不抛出异常。
    """

    def __init__(self, expressions: list[KismetExpression]) -> None:
        self._expressions = expressions
        self._offset_to_index: dict[int, int] = {}
        self._jump_targets: set[int] = set()
        self._jump_sources: dict[int, list[int]] = {}
        self._structured_indices: set[int] = set()
        self._backjump_indices: set[int] = set()
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
            target_offset: 跳转目标的偏移量。

        Returns:
            跳转到该目标的表达式索引列表，无跳转源时返回空列表。
        """
        return list(self._jump_sources.get(target_offset, []))

    # ================================================================
    # 统一模式检测入口
    # ================================================================

    def detect_pattern(self, start_idx: int) -> dict | None:
        """统一模式检测入口。按优先级尝试所有控制流模式。

        优先级顺序：
        1. for（while + 递增表达式）
        2. while（条件 + 回跳）
        3. if_else / if（条件分支）
        4. switch/case（EX_SwitchValue）

        Args:
            start_idx: 起始表达式索引。

        Returns:
            模式检测结果字典，无法匹配时返回 None。
        """
        result = self.detect_for_pattern(start_idx)
        if result is not None:
            return result
        result = self.detect_while_pattern(start_idx)
        if result is not None:
            return result
        result = self.detect_if_else_pattern(start_idx)
        if result is not None:
            return result
        result = self.detect_switch_pattern(start_idx)
        if result is not None:
            return result
        return None

    # ================================================================
    # if / if_else 检测
    # ================================================================

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

    # ================================================================
    # while 检测
    # ================================================================

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

    # ================================================================
    # for 循环检测
    # ================================================================

    def detect_for_pattern(self, start_idx: int) -> dict | None:
        """检测 for 循环控制流模式。

        UE 蓝图中 for 循环编译为：
        - 条件检查（JumpIfNot → exit）
        - 循环体（函数调用等）
        - 递增表达式（赋值语句）
        - 回跳到条件检查（EX_Jump）

        检测策略：
        1. 先匹配 while 模式（JumpIfNot + 回跳）
        2. 从回跳位置向前扫描，识别赋值类递增表达式
        3. 递增区域与循环体分离

        Returns:
            {
                "type": "for",
                "start": int,
                "condition": BooleanExpression,
                "body_start": int,
                "body_end": int,
                "increment_start": int,  # 递增表达式起始索引
                "increment_end": int,    # 递增表达式结束索引（回跳前一个）
                "exit_label": int,
            }
            无法匹配时返回 None。
        """
        while_result = self.detect_while_pattern(start_idx)
        if while_result is None:
            return None

        body_start = while_result["body_start"]
        body_end = while_result["body_end"]

        # 至少需要 body_start < body_end（有循环体内容）
        if body_end <= body_start:
            return None

        # 从回跳 EX_Jump 前一个位置向前扫描赋值类递增表达式
        inc_end = body_end - 1
        inc_start = inc_end

        # 连续的赋值表达式构成递增区域
        while inc_start > body_start and _is_assignment(self._expressions[inc_start - 1]):
            inc_start -= 1

        # 如果没有找到赋值表达式（inc_start 位置不是赋值），不满足 for 模式
        if not _is_assignment(self._expressions[inc_start]):
            return None

        # 确保循环体在递增之前有实际内容
        if inc_start <= body_start:
            # 递增从 body 开始就开始了 → 整个循环体都是递增，不像 for
            return None

        return {
            "type": "for",
            "start": while_result["start"],
            "condition": while_result["condition"],
            "body_start": body_start,
            "body_end": body_end,
            "increment_start": inc_start,
            "increment_end": inc_end,
            "exit_label": while_result["exit_label"],
        }

    # ================================================================
    # switch/case 检测
    # ================================================================

    def detect_switch_pattern(self, start_idx: int) -> dict | None:
        """检测 switch/case 控制流模式。

        UE 蓝图中 switch 语句编译为 EX_SwitchValue 表达式，内部已包含：
        - IndexTerm: switch 表达式
        - Cases: case 列表（每项含 CaseIndexValueTerm + CaseTerm）
        - DefaultTerm: 默认分支表达式

        Returns:
            {
                "type": "switch",
                "start": start_idx,
                "index_term": KismetExpression,
                "cases": [{"index_term": expr, "case_term": expr}, ...],
                "default_term": KismetExpression | None,
                "end_offset": int,
            }
            无法匹配时返回 None。
        """
        from uasset_read.kismet.expressions.special import EX_SwitchValue

        if start_idx < 0 or start_idx >= len(self._expressions):
            return None

        expr = self._expressions[start_idx]
        if not isinstance(expr, EX_SwitchValue):
            return None

        cases = []
        if expr.Cases:
            for case_item in expr.Cases:
                cases.append({
                    "index_term": case_item.CaseIndexValueTerm,
                    "case_term": case_item.CaseTerm,
                })

        return {
            "type": "switch",
            "start": start_idx,
            "index_term": expr.IndexTerm,
            "cases": cases,
            "default_term": expr.DefaultTerm,
            "end_offset": expr.EndGotoOffset,
        }

    # ================================================================
    # 回跳 / 结构化索引查询
    # ================================================================

    def is_while_backjump(self, idx: int) -> bool:
        """判断指定索引是否是某个 while/for 循环的回跳 EX_Jump。

        使用懒初始化缓存，首次调用时扫描所有 JumpIfNot 起始的 while 模式。

        Args:
            idx: 待检查的表达式索引。

        Returns:
            如果 idx 是某个 while/for 循环的回跳指令则返回 True。
        """
        if not self._backjump_indices:
            self._build_backjump_cache()
        return idx in self._backjump_indices

    def _build_backjump_cache(self) -> None:
        """构建回跳索引缓存（延迟初始化）。"""
        from uasset_read.kismet.expressions.control_flow import EX_JumpIfNot

        for start_idx in range(len(self._expressions)):
            if not isinstance(self._expressions[start_idx], EX_JumpIfNot):
                continue
            while_result = self.detect_while_pattern(start_idx)
            if while_result is not None:
                self._backjump_indices.add(while_result["body_end"])

    def get_structured_indices(self) -> set[int]:
        """获取所有属于结构化控制流块的表达式索引集合。

        包括 while/for 循环体、if/else 分支体、switch/case 内部的所有索引。
        用于 translator 跳过已结构化的表达式。

        Returns:
            结构化索引集合。
        """
        if not self._structured_indices:
            self._build_structured_indices()
        return set(self._structured_indices)

    def _build_structured_indices(self) -> None:
        """构建结构化索引集合（延迟初始化）。"""
        from uasset_read.kismet.expressions.control_flow import EX_JumpIfNot
        from uasset_read.kismet.expressions.special import EX_SwitchValue

        for idx in range(len(self._expressions)):
            expr = self._expressions[idx]

            # switch 模式：EX_SwitchValue 自身
            if isinstance(expr, EX_SwitchValue):
                self._structured_indices.add(idx)
                continue

            # JumpIfNot 起始的模式
            if isinstance(expr, EX_JumpIfNot):
                # for > while > if_else > if（优先级）
                for_result = self.detect_for_pattern(idx)
                if for_result is not None:
                    for j in range(for_result["start"], for_result["body_end"] + 1):
                        self._structured_indices.add(j)
                    continue

                while_result = self.detect_while_pattern(idx)
                if while_result is not None:
                    for j in range(while_result["start"], while_result["body_end"] + 1):
                        self._structured_indices.add(j)
                    continue

                if_else_result = self.detect_if_else_pattern(idx)
                if if_else_result is not None:
                    end = if_else_result.get(
                        "else_end",
                        if_else_result.get("then_end", if_else_result["start"]),
                    )
                    for j in range(if_else_result["start"], end + 1):
                        self._structured_indices.add(j)

    # ================================================================
    # 结构化率分析
    # ================================================================

    def analyze_structured_rate(self) -> StructuredRateReport:
        """分析控制流结构化率。

        扫描所有跳转指令，尝试匹配控制流模式，统计结构化率和 goto 回退原因。

        Returns:
            StructuredRateReport 包含结构化率、模式计数、goto 原因列表。
        """
        from uasset_read.kismet.expressions.control_flow import (
            EX_Jump, EX_JumpIfNot, EX_ComputedJump,
        )
        from uasset_read.kismet.expressions.special import EX_SwitchValue

        report = StructuredRateReport()
        pattern_counts: dict[str, int] = {}
        goto_reasons: list[dict] = []

        # 收集所有跳转指令索引
        jump_indices: list[int] = []
        for idx, expr in enumerate(self._expressions):
            if isinstance(expr, (EX_Jump, EX_JumpIfNot, EX_ComputedJump)):
                jump_indices.append(idx)
            elif isinstance(expr, EX_SwitchValue):
                jump_indices.append(idx)

        report.total_jump_exprs = len(jump_indices)
        structured_set: set[int] = set()

        for idx in jump_indices:
            expr = self._expressions[idx]

            # switch 模式
            if isinstance(expr, EX_SwitchValue):
                pattern_counts["switch"] = pattern_counts.get("switch", 0) + 1
                structured_set.add(idx)
                continue

            # 跳过 while/for 回跳（已被循环结构覆盖）
            if isinstance(expr, EX_Jump) and self.is_while_backjump(idx):
                structured_set.add(idx)
                continue

            # 尝试 for > while > if_else > if
            pattern = self.detect_pattern(idx)
            if pattern is not None:
                ptype = pattern["type"]
                pattern_counts[ptype] = pattern_counts.get(ptype, 0) + 1
                # 标记整个块的所有跳转指令为结构化
                if ptype in ("for", "while"):
                    for j in range(pattern["start"], pattern["body_end"] + 1):
                        if j in jump_indices:
                            structured_set.add(j)
                elif ptype in ("if_else", "if"):
                    end = pattern.get(
                        "else_end", pattern.get("then_end", pattern["start"]),
                    )
                    for j in range(pattern["start"], end + 1):
                        if j in jump_indices:
                            structured_set.add(j)
            else:
                # goto 回退
                reason = self._classify_goto_reason(idx, expr)
                goto_reasons.append({
                    "index": idx,
                    "reason": reason,
                    "expr_type": type(expr).__name__,
                })

        report.structured_count = len(structured_set)
        report.goto_count = report.total_jump_exprs - report.structured_count
        report.rate = (
            report.structured_count / report.total_jump_exprs
            if report.total_jump_exprs > 0
            else 1.0
        )
        report.pattern_counts = pattern_counts
        report.goto_reasons = goto_reasons

        return report

    def _classify_goto_reason(self, idx: int, expr: object) -> str:
        """分类 goto 回退的具体原因。

        Args:
            idx: 表达式索引。
            expr: 表达式对象。

        Returns:
            人类可读的回退原因字符串。
        """
        from uasset_read.kismet.expressions.control_flow import (
            EX_Jump, EX_JumpIfNot, EX_ComputedJump,
        )

        if isinstance(expr, EX_ComputedJump):
            return "computed_jump（动态计算跳转目标，无法静态分析）"

        # EX_JumpIfNot 是 EX_Jump 的子类，必须先检查
        if isinstance(expr, EX_JumpIfNot):
            target = getattr(expr, "CodeOffset", None)
            return f"unmatched_conditional（条件跳转到 offset={target}，不匹配 if/while/for 模式）"

        if isinstance(expr, EX_Jump):
            target = getattr(expr, "CodeOffset", None)
            if target is not None:
                target_idx = self.find_label_index(target)
                if target_idx is not None and target_idx > idx:
                    return f"forward_jump（前跳到 offset={target}，无匹配的结构化模式）"
                elif target_idx is not None and target_idx < idx:
                    return f"backward_jump（回跳到 offset={target}，非循环结构）"
            return "unresolved_jump（跳转目标未在表达式列表中找到）"

        return "unknown（未识别的跳转类型）"

    # ================================================================
    # goto fallback 报告生成
    # ================================================================

    def format_goto_report(self, report: StructuredRateReport | None = None) -> str:
        """格式化 goto 回退报告为可读文本。

        Args:
            report: 可选的预计算报告，为 None 时自动调用 analyze_structured_rate()。

        Returns:
            格式化的报告文本。
        """
        if report is None:
            report = self.analyze_structured_rate()

        lines: list[str] = []
        lines.append("=== 控制流结构化率报告 ===")
        lines.append(f"总跳转指令数: {report.total_jump_exprs}")
        lines.append(f"已结构化: {report.structured_count}")
        lines.append(f"goto 回退: {report.goto_count}")
        lines.append(f"结构化率: {report.rate:.1%}")
        lines.append("")

        if report.pattern_counts:
            lines.append("模式命中统计:")
            for pattern, count in sorted(report.pattern_counts.items()):
                lines.append(f"  {pattern}: {count}")
            lines.append("")

        if report.goto_reasons:
            lines.append(f"goto 回退原因 ({len(report.goto_reasons)} 条):")
            for item in report.goto_reasons:
                lines.append(f"  [{item['index']}] {item['expr_type']}: {item['reason']}")

        return "\n".join(lines)
