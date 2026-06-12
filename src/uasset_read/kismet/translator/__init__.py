"""Kismet Translator package — UE → C++ pseudocode translation.

Provides:
- TypeRegistry: UE → C++ type mapping with metadata population
- MathFunctionCleaner: Beautifies UKismetMathLibrary::Add_IntInt(a,b) → a + b
- KismetTranslator: Central dispatcher with line_cpp() for all expression types
"""
from __future__ import annotations

from .type_registry import TypeRegistry, UE_TYPE_MAP
from .math_cleaner import MathFunctionCleaner
from .translator import KismetTranslator, line_cpp

__all__ = [
    "TypeRegistry",
    "UE_TYPE_MAP",
    "MathFunctionCleaner",
    "KismetTranslator",
    "line_cpp",
]
