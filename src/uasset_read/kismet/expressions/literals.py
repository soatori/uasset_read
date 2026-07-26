"""
Kismet expression subclasses — Numeric and boolean literal constants.
"""
from __future__ import annotations

from uasset_read.kismet.expressions.base import (
    make_simple_expression, make_value_expression,
)
from uasset_read.kismet.tokens import EExprToken


# Single-value expression: read one value from the archive
EX_IntConst = make_value_expression(EExprToken.EX_IntConst, "read_i32")
EX_FloatConst = make_value_expression(EExprToken.EX_FloatConst, "read_f32")
EX_ByteConst = make_value_expression(EExprToken.EX_ByteConst, "read_u8")
EX_IntConstByte = make_value_expression(EExprToken.EX_IntConstByte, "read_u8")
EX_Int64Const = make_value_expression(EExprToken.EX_Int64Const, "read_i64")
EX_UInt64Const = make_value_expression(EExprToken.EX_UInt64Const, "read_u64")
EX_DoubleConst = make_value_expression(EExprToken.EX_DoubleConst, "read_f64")

# Data-free expression: returns Token only
EX_IntZero = make_simple_expression(EExprToken.EX_IntZero)
EX_IntOne = make_simple_expression(EExprToken.EX_IntOne)
EX_True = make_simple_expression(EExprToken.EX_True)
EX_False = make_simple_expression(EExprToken.EX_False)
EX_NoObject = make_simple_expression(EExprToken.EX_NoObject)
EX_NoInterface = make_simple_expression(EExprToken.EX_NoInterface)
EX_Self = make_simple_expression(EExprToken.EX_Self)
EX_Nothing = make_simple_expression(EExprToken.EX_Nothing)
