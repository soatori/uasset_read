"""CFG 结构化语句定义。

定义基于 CFG 区域分解的结构化语句类型，用于生成伪代码输出。
语句树反映控制流结构：Branch、Loop、Switch、Sequence、Assignment、Call、Return。
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Stmt 基类
# ---------------------------------------------------------------------------

class Stmt:
    """结构化语句基类。"""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


# ---------------------------------------------------------------------------
# 叶节点语句
# ---------------------------------------------------------------------------

@dataclass
class Assignment(Stmt):
    """赋值语句。"""

    lhs: str = ""
    rhs: str = ""

    def __repr__(self) -> str:
        return f"Assignment({self.lhs} = {self.rhs})"


@dataclass
class Call(Stmt):
    """函数调用语句。"""

    text: str = ""

    def __repr__(self) -> str:
        return f"Call({self.text})"


@dataclass
class Return(Stmt):
    """返回语句。"""

    value: str = ""

    def __repr__(self) -> str:
        return f"Return({self.value})"


@dataclass
class GotoLabel(Stmt):
    """跳转标签（goto 回退）。"""

    label: str = ""

    def __repr__(self) -> str:
        return f"GotoLabel({self.label})"


# ---------------------------------------------------------------------------
# 复合语句
# ---------------------------------------------------------------------------

@dataclass
class Sequence(Stmt):
    """语句序列（顺序执行）。"""

    stmts: list[Stmt] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Sequence({self.stmts})"


@dataclass
class Branch(Stmt):
    """条件分支语句。"""

    condition: str = ""
    then_body: Stmt | None = None
    else_body: Stmt | None = None

    def __repr__(self) -> str:
        return f"Branch({self.condition}, then={self.then_body}, else={self.else_body})"


@dataclass
class Loop(Stmt):
    """循环语句（while / do-while）。"""

    kind: str = "while"  # "while" | "do_while"
    condition: str = ""
    body: Stmt | None = None

    def __repr__(self) -> str:
        return f"Loop({self.kind}, {self.condition}, body={self.body})"


@dataclass
class Switch(Stmt):
    """switch/case 语句。"""

    expression: str = ""
    cases: list[tuple[str, Stmt]] = field(default_factory=list)
    default_body: Stmt | None = None

    def __repr__(self) -> str:
        return f"Switch({self.expression}, cases={len(self.cases)})"


__all__ = [
    "Assignment",
    "Branch",
    "Call",
    "GotoLabel",
    "Loop",
    "Return",
    "Sequence",
    "Stmt",
    "Switch",
]
