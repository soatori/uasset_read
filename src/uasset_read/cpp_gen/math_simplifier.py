"""
蓝图数学函数简化器 — KismetMathLibrary 运算符映射。

将蓝图中的 KismetMathLibrary 函数调用简化为对应的运算符表达式，
提升 C++ 代码生成的可读性和简洁性。

导出：
    MathSimplifier: 数学函数简化器类
"""
from __future__ import annotations

from typing import Optional


class MathSimplifier:
    """将 KismetMathLibrary 函数调用简化为运算符。"""

    # 运算符映射表
    OPERATOR_MAP = {
        # 算术运算
        "Add_IntInt": "+",
        "Add_FloatFloat": "+",
        "Add_DoubleDouble": "+",
        "Subtract_IntInt": "-",
        "Subtract_FloatFloat": "-",
        "Subtract_DoubleDouble": "-",
        "Multiply_IntInt": "*",
        "Multiply_FloatFloat": "*",
        "Multiply_DoubleDouble": "*",
        "Divide_IntInt": "/",
        "Divide_FloatFloat": "/",
        "Divide_DoubleDouble": "/",
        "Percent_IntInt": "%",
        "Percent_FloatFloat": "%",
        "Negate_Int": "-",
        "Negate_Float": "-",
        "Negate_Double": "-",

        # 比较运算
        "EqualEqual_IntInt": "==",
        "EqualEqual_FloatFloat": "==",
        "EqualEqual_DoubleDouble": "==",
        "NotEqual_IntInt": "!=",
        "NotEqual_FloatFloat": "!=",
        "NotEqual_DoubleDouble": "!=",
        "Greater_IntInt": ">",
        "Greater_FloatFloat": ">",
        "Greater_DoubleDouble": ">",
        "Less_IntInt": "<",
        "Less_FloatFloat": "<",
        "Less_DoubleDouble": "<",
        "GreaterEqual_IntInt": ">=",
        "GreaterEqual_FloatFloat": ">=",
        "LessEqual_IntInt": "<=",
        "LessEqual_FloatFloat": "<=",

        # 逻辑运算
        "BooleanAND": "&&",
        "BooleanOR": "||",
        "BooleanNOT": "!",

        # 向量运算
        "Add_VectorVector": "+",
        "Subtract_VectorVector": "-",
        "Multiply_VectorFloat": "*",
        "Multiply_FloatVector": "*",
        "Divide_VectorFloat": "/",

        # 数学函数 (保持函数形式)
        "Abs_Int": "FMath::Abs",
        "Abs_Float": "FMath::Abs",
        "Abs_Double": "FMath::Abs",
        "Sin": "FMath::Sin",
        "Cos": "FMath::Cos",
        "Tan": "FMath::Tan",
        "Atan": "FMath::Atan",
        "Atan2": "FMath::Atan2",
        "Sqrt": "FMath::Sqrt",
        "Pow": "FMath::Pow",
        "FMin": "FMath::Min",
        "FMax": "FMath::Max",
        "FClamp": "FMath::Clamp",
    }

    # 前缀映射 (用于类型变体)
    TYPE_PREFIXES = ["Int", "Float", "Double", "Byte"]

    def simplify(self, function_name: str) -> Optional[str]:
        """简化函数名为运算符。"""
        # 直接查找
        if function_name in self.OPERATOR_MAP:
            return self.OPERATOR_MAP[function_name]

        # 尝试去除类型后缀查找
        for prefix in self.TYPE_PREFIXES:
            for op_name, op_symbol in self.OPERATOR_MAP.items():
                if op_name.endswith(prefix) and function_name == op_name[:-len(prefix)]:
                    return op_symbol

        return None

    def is_math_library_function(self, function_name: str) -> bool:
        """检查是否为 KismetMathLibrary 函数。"""
        return function_name in self.OPERATOR_MAP

    def get_operator_info(self, function_name: str) -> Optional[dict]:
        """获取运算符详细信息。"""
        if function_name not in self.OPERATOR_MAP:
            return None

        op = self.OPERATOR_MAP[function_name]

        # 判断运算符类型
        if op in ["+", "-", "*", "/", "%"]:
            return {"type": "arithmetic", "operator": op}
        elif op in ["==", "!=", ">", "<", ">=", "<="]:
            return {"type": "comparison", "operator": op}
        elif op in ["&&", "||", "!"]:
            return {"type": "logical", "operator": op}
        else:
            return {"type": "function", "function": op}