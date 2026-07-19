"""
Kismet 表达式系统 — 基类定义。

包含 KismetExpression 抽象基类和 KismetExpressionT 泛型子类。
"""


from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from uasset_read.kismet.tokens import EExprToken

T = TypeVar("T")


class KismetExpression(ABC):
    """
    Kismet 字节码表达式抽象基类。

    所有 EX_* 指令的解析结果都继承此类。
    子类必须实现 Token 属性并定义 from_archive 类方法。
    """

    StatementIndex: int

    def __init__(self, statement_index: int = 0) -> None:
        self.StatementIndex = statement_index

    @property
    @abstractmethod
    def Token(self) -> EExprToken:
        """返回此表达式对应的 EExprToken 值。"""
        ...

    def to_dict(self) -> dict:
        """序列化为字典格式（用于 JSON 输出）。"""
        return {
            "Inst": self.Token.name,
            "StatementIndex": self.StatementIndex,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} token={self.Token.name}>"


@dataclass(kw_only=True)
class KismetExpressionT(KismetExpression, Generic[T]):
    """
    携带值的 Kismet 表达式泛型基类。

    适用于具有关联数据（常量、变量引用等）的表达式。

    Uses kw_only=True so subclasses can freely pass Value=... from
    from_archive() without positional-argument conflicts.
    """

    value: T = field(default=None)  # type: ignore[assignment]
    Value: T = field(default=None)  # alias accepted by from_archive()

    def __init__(self, *, value: T = None, Value: T = None, statement_index: int = 0) -> None:  # type: ignore[assignment]
        KismetExpression.__init__(self, statement_index)
        # Prefer explicit Value= (from_archive convention), fall back to value=
        resolved = Value if Value is not None else value
        self.value = resolved
        self.Value = resolved

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Value"] = self.Value
        return result

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} token={self.Token.name} value={self.Value!r}>"


def make_simple_expression(token: EExprToken):
    """创建简单表达式类（无额外字段，仅返回 Token 值）。

    用于 EX_Nothing, EX_IntZero, EX_IntOne 等无数据的表达式。
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
    """创建带值的表达式类（从 archive 读取单个值）。

    用于 EX_IntConst, EX_FloatConst 等读取单个值的表达式。

    Args:
        token: 对应的 EExprToken 枚举值
        read_func_name: FArchive 上的读取方法名（如 "read_i32", "read_f32"）
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
