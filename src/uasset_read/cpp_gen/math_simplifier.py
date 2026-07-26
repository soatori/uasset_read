"""
Blueprint math function simplifier -- KismetMathLibrary operator mapping.

Simplifies KismetMathLibrary function calls in blueprints to corresponding operator expressions,
improving readability and conciseness of generated C++ code.

Exports:
    MathSimplifier: Math function simplifier class
"""

from typing import Optional


class MathSimplifier:
    """Simplify KismetMathLibrary function calls to operators."""

    # Operator mapping table
    OPERATOR_MAP = {
        # Arithmetic operations
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

        # Comparison operations
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

        # Logical operations
        "BooleanAND": "&&",
        "BooleanOR": "||",
        "BooleanNOT": "!",

        # Vector operations
        "Add_VectorVector": "+",
        "Subtract_VectorVector": "-",
        "Multiply_VectorFloat": "*",
        "Multiply_FloatVector": "*",
        "Divide_VectorFloat": "/",

        # Math functions (keep as function form)
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

    # Prefix mapping (for type variants)
    TYPE_PREFIXES = ["Int", "Float", "Double", "Byte"]

    def simplify(self, function_name: str) -> Optional[str]:
        """Simplify function name to operator."""
        # Direct lookup
        if function_name in self.OPERATOR_MAP:
            return self.OPERATOR_MAP[function_name]

        # Try removing type suffix for lookup
        for prefix in self.TYPE_PREFIXES:
            for op_name, op_symbol in self.OPERATOR_MAP.items():
                if op_name.endswith(prefix) and function_name == op_name[:-len(prefix)]:
                    return op_symbol

        return None

    def is_math_library_function(self, function_name: str) -> bool:
        """Check if it is a KismetMathLibrary function."""
        return function_name in self.OPERATOR_MAP

    def get_operator_info(self, function_name: str) -> Optional[dict]:
        """Get detailed operator information."""
        if function_name not in self.OPERATOR_MAP:
            return None

        op = self.OPERATOR_MAP[function_name]

        # Determine operator type
        if op in ["+", "-", "*", "/", "%"]:
            return {"type": "arithmetic", "operator": op}
        elif op in ["==", "!=", ">", "<", ">=", "<="]:
            return {"type": "comparison", "operator": op}
        elif op in ["&&", "||", "!"]:
            return {"type": "logical", "operator": op}
        else:
            return {"type": "function", "function": op}