"""CFG structured statement definitions.

Defines structured statement types based on CFG region decomposition,
used for generating pseudocode output.
Statement tree reflects control flow structure: Branch, Loop, Switch,
Sequence, Assignment, Call, Return.
"""


from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Stmt base class
# ---------------------------------------------------------------------------

class Stmt:
    """Structured statement base class."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


# ---------------------------------------------------------------------------
# Leaf node statements
# ---------------------------------------------------------------------------

@dataclass
class Assignment(Stmt):
    """Assignment statement."""

    lhs: str = ""
    rhs: str = ""

    def __repr__(self) -> str:
        return f"Assignment({self.lhs} = {self.rhs})"


@dataclass
class Call(Stmt):
    """Function call statement."""

    text: str = ""

    def __repr__(self) -> str:
        return f"Call({self.text})"


@dataclass
class Return(Stmt):
    """Return statement."""

    value: str = ""

    def __repr__(self) -> str:
        return f"Return({self.value})"


@dataclass
class GotoLabel(Stmt):
    """Jump label (goto fallback)."""

    label: str = ""

    def __repr__(self) -> str:
        return f"GotoLabel({self.label})"


# ---------------------------------------------------------------------------
# Compound statements
# ---------------------------------------------------------------------------

@dataclass
class Sequence(Stmt):
    """Statement sequence (sequential execution)."""

    stmts: list[Stmt] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Sequence({self.stmts})"


@dataclass
class Branch(Stmt):
    """Conditional branch statement."""

    condition: str = ""
    then_body: Stmt | None = None
    else_body: Stmt | None = None

    def __repr__(self) -> str:
        return f"Branch({self.condition}, then={self.then_body}, else={self.else_body})"


@dataclass
class Loop(Stmt):
    """Loop statement (while / do-while)."""

    kind: str = "while"  # "while" | "do_while"
    condition: str = ""
    body: Stmt | None = None

    def __repr__(self) -> str:
        return f"Loop({self.kind}, {self.condition}, body={self.body})"


@dataclass
class Switch(Stmt):
    """switch/case statement."""

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
