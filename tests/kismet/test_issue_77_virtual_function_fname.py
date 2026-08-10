"""Test for Issue #77: EX_VirtualFunction FName fix.

Verifies that EX_VirtualFunction reads FName (NameIndex + Number) instead of FString.
"""

from __future__ import annotations

import struct
from io import BytesIO

from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions.functions import EX_VirtualFunction
from uasset_read.kismet.tokens import EExprToken


def test_virtual_function_reads_fname():
    """EX_VirtualFunction should read FName (NameIndex + Number), not FString."""
    # Create a minimal bytecode stream with EX_VirtualFunction
    # Token: 0x1B (EX_VirtualFunction)
    # FName: NameIndex=4, Number=0
    # EndFunctionParms: 0x1E

    name_map = ["None", "TestFunction", "OtherFunc", "AnotherFunc", "VirtualFunc"]

    bytecode = bytearray()
    bytecode.append(EExprToken.EX_VirtualFunction)  # 0x1B
    bytecode.extend(struct.pack('<i', 4))   # NameIndex
    bytecode.extend(struct.pack('<i', 0))   # Number
    bytecode.append(EExprToken.EX_EndFunctionParms)  # 0x1E

    archive = FKismetArchive(bytes(bytecode), "test", name_map, tolerant=False)
    expr = archive.read_expression()

    assert isinstance(expr, EX_VirtualFunction)
    assert expr.VirtualFunctionName == "VirtualFunc"
    assert expr.Parameters == []


def test_virtual_function_fname_with_number():
    """EX_VirtualFunction should handle FName with non-zero Number."""
    name_map = ["None", "TestFunc"]

    bytecode = bytearray()
    bytecode.append(EExprToken.EX_VirtualFunction)  # 0x1B
    bytecode.extend(struct.pack('<i', 1))   # NameIndex
    bytecode.extend(struct.pack('<i', 3))   # Number = 3
    bytecode.append(EExprToken.EX_EndFunctionParms)  # 0x1E

    archive = FKismetArchive(bytes(bytecode), "test", name_map, tolerant=False)
    expr = archive.read_expression()

    assert isinstance(expr, EX_VirtualFunction)
    # With Number > 0, should append _Number suffix
    assert expr.VirtualFunctionName == "TestFunc_3"
