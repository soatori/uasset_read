"""
Kismet expression system -- base class definitions.

Contains the KismetExpression abstract base class and the KismetExpressionT generic subclass.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from uasset_read.kismet.tokens import EExprToken

T = TypeVar("T")


class KismetExpression(ABC):
    """
    Kismet bytecode expression abstract base class.

    All EX_* instruction parse results inherit from this class.
    Subclasses must implement the Token property and define a from_archive classmethod.
    """

    StatementIndex: int

    def __init__(self, statement_index: int = 0) -> None:
        self.StatementIndex = statement_index

    @property
    @abstractmethod
    def Token(self) -> EExprToken:
        """Return the EExprToken value corresponding to this expression."""
        ...

    def to_dict(self) -> dict:
        """Serialize to dictionary format (for JSON output)."""
        return {
            "Inst": self.Token.name,
            "StatementIndex": self.StatementIndex,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} token={self.Token.name}>"


@dataclass(kw_only=True)
class KismetExpressionT(KismetExpression, Generic[T]):
    """
    Generic base class for Kismet expressions that carry a value.

    Suitable for expressions with associated data (constants, variable references, etc.).

    Uses kw_only=True so subclasses can freely pass Value=... from
    from_archive() without positional-argument conflicts.
    """

    Value: T = field(default=None)  # type: ignore[assignment]

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Value"] = self.Value
        return result

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} token={self.Token.name} value={self.Value!r}>"


def make_simple_expression(token: EExprToken):
    """Create a simple expression class (no extra fields, only returns Token value).

    Used for EX_Nothing, EX_IntZero, EX_IntOne and other data-free expressions.
    """

    @dataclass
    class _SimpleExpr(KismetExpression):
        @property
        def Token(self) -> EExprToken:
            return token

    _SimpleExpr.__name__ = token.name
    _SimpleExpr.__qualname__ = token.name
    return _SimpleExpr


def make_value_expression(token: EExprToken, read_func_name: str):
    """Create a value-carrying expression class (reads a single value from the archive).

    Used for EX_IntConst, EX_FloatConst and other single-value expressions.

    Args:
        token: The corresponding EExprToken enum value.
        read_func_name: The read method name on FArchive (e.g. "read_i32", "read_f32").
    """

    @dataclass
    class _ValueExpr(KismetExpressionT):
        @property
        def Token(self) -> EExprToken:
            return token

        @classmethod
        def from_archive(cls, archive, name_map):
            reader = getattr(archive, read_func_name)
            return cls(Value=reader())

    _ValueExpr.__name__ = token.name
    _ValueExpr.__qualname__ = token.name
    return _ValueExpr
