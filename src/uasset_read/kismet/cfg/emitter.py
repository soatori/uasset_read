"""CFG 结构化伪代码发射器。

从 RegionTree 解码 CFG 区域结构，生成结构化语句树，再渲染为伪代码。
算法：
1. DFS 遍历 RegionTree，按 RegionKind 调用对应 emit 函数
2. emit_body() 递归渲染 Stmt 树，缩进管理
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from uasset_read.kismet.cfg.data import BasicBlock, CFG, EdgeKind, Region, RegionKind, RegionTree
from uasset_read.kismet.cfg.stmt import (
    Assignment,
    Branch,
    Call,
    GotoLabel,
    Loop,
    Return,
    Sequence,
    Stmt,
    Switch,
)

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.kismet.translator import KismetTranslator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 区域解码器
# ---------------------------------------------------------------------------

class RegionDecoder:
    """DFS 遍历 RegionTree，将区域分解为结构化语句树。

    对每种 RegionKind 调用对应的 emit 方法，生成 Stmt 节点。
    """

    def __init__(
        self,
        cfg: CFG,
        region_tree: RegionTree,
        expressions: list[KismetExpression],
        translator: KismetTranslator,
        offset_to_index: dict[int, int],
        jump_targets: set[int],
    ) -> None:
        self.cfg = cfg
        self.region_tree = region_tree
        self.expressions = expressions
        self.translator = translator
        self.offset_to_index = offset_to_index
        self.jump_targets = jump_targets
        self._decoded_regions: set[int] = set()  # 已解码的区域 ID，防止递归

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def decode(self) -> Stmt:
        """从 root 区域开始解码，返回完整语句树。"""
        self._decoded_regions.clear()
        root = self.region_tree.root
        if root is None:
            return Sequence()
        return self._decode_region(root)

    # ------------------------------------------------------------------
    # 按 RegionKind 分发
    # ------------------------------------------------------------------

    def _decode_region(self, region: Region) -> Stmt:
        """解码单个区域。"""
        if region.region_id in self._decoded_regions:
            # 已解码过，回退为基本块输出
            return self._emit_block(region)
        self._decoded_regions.add(region.region_id)
        kind = region.kind

        if kind == RegionKind.BLOCK:
            return self._emit_block(region)
        elif kind == RegionKind.IF_THEN:
            return self._emit_if_then(region)
        elif kind == RegionKind.IF_THEN_ELSE:
            return self._emit_if_then_else(region)
        elif kind in (RegionKind.WHILE_LOOP, RegionKind.DO_WHILE):
            return self._emit_loop(region, kind)
        elif kind == RegionKind.FOR_LOOP:
            return self._emit_loop(region, kind)
        elif kind == RegionKind.SELF_LOOP:
            return self._emit_self_loop(region)
        elif kind == RegionKind.IRREDUCIBLE:
            return self._emit_block(region)
        else:
            return self._emit_block(region)

    # ------------------------------------------------------------------
    # BLOCK：直线序列
    # ------------------------------------------------------------------

    def _emit_block(self, region: Region) -> Sequence:
        """发射 BLOCK 区域（直线序列）。"""
        stmts: list[Stmt] = []
        for bid in region.body_blocks:
            block = self.cfg.blocks.get(bid)
            if block is None:
                continue
            stmts.extend(self._emit_basic_block(block))
        return Sequence(stmts=stmts)

    def _emit_basic_block(self, block: BasicBlock) -> list[Stmt]:
        """发射单个基本块的语句。"""
        stmts: list[Stmt] = []
        for idx in range(block.start_idx, block.end_idx + 1):
            if idx >= len(self.expressions):
                continue
            expr = self.expressions[idx]
            cpp_line = self.translator.line_cpp(expr, index=idx)
            if not cpp_line or not cpp_line.strip():
                continue
            stripped = cpp_line.strip()
            stmts.append(self._line_to_stmt(stripped))
        return stmts

    def _line_to_stmt(self, line: str) -> Stmt:
        """将单行 C++ 伪代码转换为 Stmt。"""
        # 跳转标签
        if line.startswith("Label_"):
            return GotoLabel(label=line)
        # 赋值检测: 包含 = 但不以 if/for/while/switch 开头
        if (
            "=" in line
            and not line.startswith("if ")
            and not line.startswith("for ")
            and not line.startswith("while ")
            and not line.startswith("switch ")
            and not line.startswith("else")
        ):
            parts = line.split("=", 1)
            lhs = parts[0].strip()
            rhs = parts[1].strip().rstrip(";")
            if lhs and rhs:
                return Assignment(lhs=lhs, rhs=rhs)
        # return
        if line.startswith("return"):
            value = line.removeprefix("return").strip().rstrip(";")
            return Return(value=value)
        # 其他作为调用或语句
        return Call(text=line)

    # ------------------------------------------------------------------
    # IF_THEN：单分支
    # ------------------------------------------------------------------

    def _emit_if_then(self, region: Region) -> Branch:
        """发射 IF_THEN 区域。"""
        condition = self._get_head_condition(region)
        then_body = self._emit_body_for_blocks(region, region.body_blocks)
        return Branch(condition=condition, then_body=then_body, else_body=None)

    # ------------------------------------------------------------------
    # IF_THEN_ELSE：双分支
    # ------------------------------------------------------------------

    def _emit_if_then_else(self, region: Region) -> Branch:
        """发射 IF_THEN_ELSE 区域。"""
        condition = self._get_head_condition(region)

        # 区分 then/else 分支块
        head = region.head
        then_blocks: list[int] = []
        else_blocks: list[int] = []

        block = self.cfg.blocks.get(head)
        if block is not None and len(block.successors) >= 2:
            # 根据边类型区分 then/else
            for succ in block.successors:
                kind = block.edge_kinds.get(succ)
                if kind == EdgeKind.CONDITIONAL:
                    # CONDITIONAL → then 分支
                    then_blocks.append(succ)
                elif kind == EdgeKind.FALSE_BRANCH:
                    # FALSE_BRANCH → else 分支
                    else_blocks.append(succ)
                else:
                    then_blocks.append(succ)
        else:
            # 回退：前半 then，后半 else
            mid = len(region.body_blocks) // 2
            then_blocks = region.body_blocks[:mid]
            else_blocks = region.body_blocks[mid:]

        then_body = self._emit_body_for_blocks(region, then_blocks)
        else_body = self._emit_body_for_blocks(region, else_blocks)
        return Branch(condition=condition, then_body=then_body, else_body=else_body)

    # ------------------------------------------------------------------
    # LOOP
    # ------------------------------------------------------------------

    def _emit_loop(self, region: Region, kind: RegionKind) -> Loop:
        """发射循环区域。"""
        condition = self._get_head_condition(region)
        body_blocks = [b for b in region.body_blocks if b != region.head]
        if not body_blocks:
            body_blocks = region.body_blocks
        body = self._emit_body_for_blocks(region, body_blocks)

        if kind == RegionKind.DO_WHILE:
            loop_kind = "do_while"
        elif kind == RegionKind.FOR_LOOP:
            loop_kind = "for"
        else:
            loop_kind = "while"

        return Loop(kind=loop_kind, condition=condition, body=body)

    # ------------------------------------------------------------------
    # SELF_LOOP：单块自循环
    # ------------------------------------------------------------------

    def _emit_self_loop(self, region: Region) -> Loop:
        """发射自循环区域。"""
        condition = self._get_head_condition(region)
        stmts = self._emit_basic_block_for_region(region, region.head)
        body = Sequence(stmts=stmts) if stmts else Sequence(stmts=[])
        return Loop(kind="while", condition=condition, body=body)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _get_head_condition(self, region: Region) -> str:
        """获取区域头部块的条件表达式。"""
        block = self.cfg.blocks.get(region.head)
        if block is None:
            return "true"
        for idx in range(block.start_idx, block.end_idx + 1):
            if idx >= len(self.expressions):
                continue
            expr = self.expressions[idx]
            if hasattr(expr, "CodeOffset"):
                cpp_line = self.translator.line_cpp(expr, index=idx)
                if cpp_line and cpp_line.strip():
                    line = cpp_line.strip()
                    # 去掉尾部分号
                    line = line.rstrip(";")
                    return line
        return "true"

    def _emit_body_for_blocks(
        self, region: Region, block_ids: list[int]
    ) -> Sequence:
        """为指定块集合发射语句序列。"""
        stmts: list[Stmt] = []
        for bid in block_ids:
            if bid == self.cfg.exit_id:
                continue
            block = self.cfg.blocks.get(bid)
            if block is None:
                continue
            # 递归解码子区域
            child_region = self._find_child_region(bid)
            if child_region is not None:
                stmts.append(self._decode_region(child_region))
            else:
                stmts.extend(self._emit_basic_block(block))
        return Sequence(stmts=stmts)

    def _emit_basic_block_for_region(
        self, region: Region, bid: int
    ) -> list[Stmt]:
        """发射指定块的语句。"""
        block = self.cfg.blocks.get(bid)
        if block is None:
            return []
        return self._emit_basic_block(block)

    def _find_child_region(self, block_id: int) -> Region | None:
        """查找包含指定块的未解码子区域（更精确的区域优先）。"""
        best: Region | None = None
        for region in self.region_tree.regions.values():
            if region.region_id in self._decoded_regions:
                continue
            if block_id in region.body_blocks and region.block_count > 1:
                if best is None or region.block_count < best.block_count:
                    best = region
        return best


# ---------------------------------------------------------------------------
# 伪代码发射器
# ---------------------------------------------------------------------------

class StmtEmitter:
    """递归渲染 Stmt 树为缩进伪代码。"""

    def __init__(self, indent: str = "    ") -> None:
        self._indent = indent

    def emit_body(self, stmt: Stmt) -> str:
        """将 Stmt 树渲染为缩进伪代码字符串。"""
        return self._emit(stmt, depth=0)

    def emit_lines(self, stmt: Stmt) -> list[str]:
        """将 Stmt 树渲染为行列表。"""
        text = self.emit_body(stmt)
        return text.split("\n") if text else []

    # ------------------------------------------------------------------
    # 递归渲染
    # ------------------------------------------------------------------

    def _emit(self, stmt: Stmt, depth: int) -> str:
        """递归渲染单个语句。"""
        prefix = self._indent * depth

        if isinstance(stmt, Sequence):
            return self._emit_sequence(stmt, depth)
        elif isinstance(stmt, Branch):
            return self._emit_branch(stmt, depth)
        elif isinstance(stmt, Loop):
            return self._emit_loop(stmt, depth)
        elif isinstance(stmt, Switch):
            return self._emit_switch(stmt, depth)
        elif isinstance(stmt, Assignment):
            return f"{prefix}{stmt.lhs} = {stmt.rhs};"
        elif isinstance(stmt, Call):
            text = stmt.text.rstrip(";")
            return f"{prefix}{text};"
        elif isinstance(stmt, Return):
            if stmt.value:
                return f"{prefix}return {stmt.value};"
            return f"{prefix}return;"
        elif isinstance(stmt, GotoLabel):
            return f"{prefix}{stmt.label}:"
        else:
            return f"{prefix}/* unknown stmt: {type(stmt).__name__} */"

    def _emit_sequence(self, seq: Sequence, depth: int) -> str:
        """渲染语句序列。"""
        lines: list[str] = []
        for s in seq.stmts:
            rendered = self._emit(s, depth)
            if rendered:
                lines.append(rendered)
        return "\n".join(lines)

    def _emit_branch(self, branch: Branch, depth: int) -> str:
        """渲染 if/else 分支。"""
        prefix = self._indent * depth
        cond = branch.condition.rstrip(";")
        lines: list[str] = []

        lines.append(f"{prefix}if ({cond}) {{")
        if branch.then_body is not None:
            body_text = self._emit(branch.then_body, depth + 1)
            if body_text:
                lines.append(body_text)
        lines.append(f"{prefix}}}")

        if branch.else_body is not None:
            lines.append(f"{prefix}else {{")
            body_text = self._emit(branch.else_body, depth + 1)
            if body_text:
                lines.append(body_text)
            lines.append(f"{prefix}}}")

        return "\n".join(lines)

    def _emit_loop(self, loop: Loop, depth: int) -> str:
        """渲染循环语句。"""
        prefix = self._indent * depth
        cond = loop.condition.rstrip(";")
        lines: list[str] = []

        if loop.kind == "do_while":
            lines.append(f"{prefix}do {{")
            if loop.body is not None:
                body_text = self._emit(loop.body, depth + 1)
                if body_text:
                    lines.append(body_text)
            lines.append(f"{prefix}}} while ({cond});")
        elif loop.kind == "for":
            lines.append(f"{prefix}for (;;) {{")
            if loop.body is not None:
                body_text = self._emit(loop.body, depth + 1)
                if body_text:
                    lines.append(body_text)
            lines.append(f"{prefix}}}")
        else:
            # while
            lines.append(f"{prefix}while ({cond}) {{")
            if loop.body is not None:
                body_text = self._emit(loop.body, depth + 1)
                if body_text:
                    lines.append(body_text)
            lines.append(f"{prefix}}}")

        return "\n".join(lines)

    def _emit_switch(self, switch: Switch, depth: int) -> str:
        """渲染 switch/case 语句。"""
        prefix = self._indent * depth
        expr = switch.expression.rstrip(";")
        lines: list[str] = []

        lines.append(f"{prefix}switch ({expr}) {{")
        for case_val, case_body in switch.cases:
            lines.append(f"{prefix}    case {case_val}: {{")
            body_text = self._emit(case_body, depth + 2)
            if body_text:
                lines.append(body_text)
            lines.append(f"{prefix}        break;")
            lines.append(f"{prefix}    }}")
        if switch.default_body is not None:
            lines.append(f"{prefix}    default: {{")
            body_text = self._emit(switch.default_body, depth + 2)
            if body_text:
                lines.append(body_text)
            lines.append(f"{prefix}    }}")
        lines.append(f"{prefix}}}")

        return "\n".join(lines)


__all__ = ["RegionDecoder", "StmtEmitter"]
